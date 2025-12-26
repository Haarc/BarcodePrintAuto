"""
GUI интерфейс для автоматизации печати штрихкодов Ozon FBO
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import logging
from pathlib import Path
from typing import Optional

from config import Config
from ozon_api import OzonAPI, OzonAPIError
from pdf_processor import PDFProcessor, PDFProcessorError


class TextHandler(logging.Handler):
    """Обработчик логов для вывода в текстовое поле"""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.configure(state='disabled')
        self.text_widget.see(tk.END)


class OzonBarcodeGUI:
    """Главный класс GUI приложения"""

    def __init__(self, root):
        self.root = root
        self.root.title("Ozon FBO - Автоматизация печати штрихкодов")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # Переменные
        self.order_number_var = tk.StringVar()
        self.zip_path_var = tk.StringVar()
        self.auto_print_var = tk.BooleanVar(value=False)
        self.printer_name_var = tk.StringVar(value=Config.DEFAULT_PRINTER)

        # Флаг выполнения
        self.is_processing = False

        # Создание интерфейса
        self.create_widgets()
        self.setup_logging()

        # Проверка конфигурации при запуске
        self.check_config()

    def create_widgets(self):
        """Создать виджеты интерфейса"""

        # Стиль
        style = ttk.Style()
        style.theme_use('clam')

        # Главный контейнер
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Конфигурация растяжения
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Заголовок
        title_label = ttk.Label(
            main_frame,
            text="Автоматизация печати штрихкодов Ozon FBO",
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 20))

        # Фрейм ввода данных
        input_frame = ttk.LabelFrame(main_frame, text="Данные заказа", padding="10")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        # Номер заказа
        ttk.Label(input_frame, text="Номер заказа:").grid(row=0, column=0, sticky=tk.W, pady=5)
        order_number_entry = ttk.Entry(input_frame, textvariable=self.order_number_var, width=30)
        order_number_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        # Подсказка
        hint_label = ttk.Label(
            input_frame,
            text="(например: 2000038642317)",
            font=("Arial", 8),
            foreground="gray"
        )
        hint_label.grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

        # ZIP архив
        ttk.Label(input_frame, text="ZIP архив:").grid(row=1, column=0, sticky=tk.W, pady=5)
        zip_frame = ttk.Frame(input_frame)
        zip_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        zip_frame.columnconfigure(0, weight=1)

        zip_entry = ttk.Entry(zip_frame, textvariable=self.zip_path_var)
        zip_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))

        browse_btn = ttk.Button(zip_frame, text="Обзор...", command=self.browse_zip)
        browse_btn.grid(row=0, column=1, padx=(5, 0))

        # Фрейм настроек печати
        print_frame = ttk.LabelFrame(main_frame, text="Настройки печати", padding="10")
        print_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        print_frame.columnconfigure(1, weight=1)

        # Автоматическая печать
        auto_print_check = ttk.Checkbutton(
            print_frame,
            text="Автоматически отправить на печать",
            variable=self.auto_print_var,
            command=self.toggle_printer_entry
        )
        auto_print_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Принтер
        ttk.Label(print_frame, text="Принтер:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.printer_entry = ttk.Entry(print_frame, textvariable=self.printer_name_var)
        self.printer_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        self.printer_entry.configure(state='disabled')

        # Кнопки действий
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.process_btn = ttk.Button(
            button_frame,
            text="Обработать заказ",
            command=self.process_supply,
            style='Accent.TButton'
        )
        self.process_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.validate_btn = ttk.Button(
            button_frame,
            text="Проверить API",
            command=self.validate_api
        )
        self.validate_btn.pack(side=tk.LEFT, padx=(0, 5))

        clear_btn = ttk.Button(
            button_frame,
            text="Очистить",
            command=self.clear_form
        )
        clear_btn.pack(side=tk.LEFT)

        # Прогресс бар
        self.progress = ttk.Progressbar(
            main_frame,
            mode='indeterminate',
            length=300
        )
        self.progress.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Лог
        log_frame = ttk.LabelFrame(main_frame, text="Лог выполнения", padding="10")
        log_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            height=15,
            state='disabled',
            font=("Consolas", 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Статус бар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

    def setup_logging(self):
        """Настроить вывод логов в текстовое поле"""
        text_handler = TextHandler(self.log_text)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        text_handler.setFormatter(formatter)

        # Добавляем обработчик к корневому логгеру
        logger = logging.getLogger()
        logger.addHandler(text_handler)

    def check_config(self):
        """Проверить конфигурацию при запуске"""
        errors = Config.validate()
        if errors:
            self.log_message("ПРЕДУПРЕЖДЕНИЕ: Проблемы с конфигурацией:", level='WARNING')
            for error in errors:
                self.log_message(f"  - {error}", level='WARNING')
            self.log_message("Настройте .env файл для работы с API", level='WARNING')

    def log_message(self, message: str, level: str = 'INFO'):
        """Добавить сообщение в лог"""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"[{level}] {message}\n")
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)

    def browse_zip(self):
        """Открыть диалог выбора ZIP файла"""
        filename = filedialog.askopenfilename(
            title="Выберите ZIP архив со штрихкодами",
            filetypes=[
                ("ZIP архивы", "*.zip"),
                ("Все файлы", "*.*")
            ]
        )
        if filename:
            self.zip_path_var.set(filename)

    def toggle_printer_entry(self):
        """Включить/выключить поле ввода принтера"""
        if self.auto_print_var.get():
            self.printer_entry.configure(state='normal')
        else:
            self.printer_entry.configure(state='disabled')

    def validate_inputs(self) -> bool:
        """Проверить корректность введенных данных"""
        order_number = self.order_number_var.get().strip()
        zip_path = self.zip_path_var.get().strip()

        if not order_number:
            messagebox.showerror("Ошибка", "Введите номер заказа")
            return False

        if not zip_path:
            messagebox.showerror("Ошибка", "Выберите ZIP архив")
            return False

        if not Path(zip_path).exists():
            messagebox.showerror("Ошибка", f"Файл не найден:\n{zip_path}")
            return False

        return True

    def set_processing(self, is_processing: bool):
        """Установить состояние обработки"""
        self.is_processing = is_processing

        if is_processing:
            self.process_btn.configure(state='disabled')
            self.validate_btn.configure(state='disabled')
            self.progress.start(10)
            self.status_var.set("Обработка...")
        else:
            self.process_btn.configure(state='normal')
            self.validate_btn.configure(state='normal')
            self.progress.stop()
            self.status_var.set("Готов к работе")

    def process_supply(self):
        """Обработать заказ"""
        if not self.validate_inputs():
            return

        # Запускаем в отдельном потоке
        thread = threading.Thread(target=self._process_supply_thread)
        thread.daemon = True
        thread.start()

    def _process_supply_thread(self):
        """Поток обработки заказа"""
        try:
            self.set_processing(True)

            order_number = self.order_number_var.get().strip()
            zip_path = self.zip_path_var.get().strip()
            auto_print = self.auto_print_var.get()
            printer_name = self.printer_name_var.get().strip() if auto_print else None

            logger = logging.getLogger(__name__)
            logger.info(f"Начало обработки заказа {order_number}")

            # API - полный цикл: list -> get -> bundle
            api = OzonAPI()
            supply_data = api.get_supply_items_by_order_number(order_number)

            if not supply_data or not supply_data.get('items'):
                messagebox.showerror("Ошибка", "Заказ не содержит товаров")
                return

            items = supply_data['items']

            # Статистика
            logger.info(f"Уникальных товаров: {supply_data['total_unique']}")
            logger.info(f"Всего к печати: {supply_data['total_quantity']}")

            # PDF обработка
            with PDFProcessor() as processor:
                pdf_dir = processor.extract_zip(zip_path)
                output_path = Config.get_output_filepath(order_number)
                merge_stats = processor.merge_pdfs(items, pdf_dir, output_path)

                logger.info(f"Создано страниц: {merge_stats['total_pages']}")
                logger.info(f"Файл сохранен: {output_path}")

                if merge_stats['skipped_items'] > 0:
                    logger.warning(f"Пропущено товаров: {merge_stats['skipped_items']}")

                # Печать
                if auto_print:
                    if processor.print_pdf(output_path, printer_name):
                        logger.info("Файл успешно отправлен на печать")
                    else:
                        logger.warning("Не удалось отправить файл на печать")

            messagebox.showinfo(
                "Успех",
                f"Обработка завершена!\n\n"
                f"Создано страниц: {merge_stats['total_pages']}\n"
                f"Файл: {output_path.name}"
            )

        except OzonAPIError as e:
            logger.error(f"Ошибка API: {str(e)}")
            messagebox.showerror("Ошибка API", str(e))

        except PDFProcessorError as e:
            logger.error(f"Ошибка обработки PDF: {str(e)}")
            messagebox.showerror("Ошибка обработки PDF", str(e))

        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
            messagebox.showerror("Ошибка", f"Неожиданная ошибка:\n{str(e)}")

        finally:
            self.set_processing(False)

    def validate_api(self):
        """Проверить API credentials"""
        thread = threading.Thread(target=self._validate_api_thread)
        thread.daemon = True
        thread.start()

    def _validate_api_thread(self):
        """Поток проверки API"""
        try:
            self.set_processing(True)

            logger = logging.getLogger(__name__)
            logger.info("Проверка API credentials...")

            api = OzonAPI()
            if api.validate_credentials():
                logger.info("API credentials корректны")
                messagebox.showinfo("Успех", "API credentials корректны")
            else:
                logger.error("Некорректные API credentials")
                messagebox.showerror("Ошибка", "Некорректные API credentials")

        except Exception as e:
            logger.error(f"Ошибка проверки API: {str(e)}")
            messagebox.showerror("Ошибка", f"Ошибка проверки API:\n{str(e)}")

        finally:
            self.set_processing(False)

    def clear_form(self):
        """Очистить форму"""
        self.order_number_var.set("")
        self.zip_path_var.set("")
        self.auto_print_var.set(False)
        self.printer_name_var.set(Config.DEFAULT_PRINTER)
        self.toggle_printer_entry()

        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

        self.status_var.set("Готов к работе")


def main():
    """Запуск GUI приложения"""
    root = tk.Tk()
    app = OzonBarcodeGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
