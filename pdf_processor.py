"""
Модуль для обработки PDF файлов со штрихкодами
"""
import logging
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from PyPDF2 import PdfReader, PdfWriter
import platform

logger = logging.getLogger(__name__)


class PDFProcessorError(Exception):
    """Исключение для ошибок обработки PDF"""
    pass


class PDFProcessor:
    """Класс для обработки PDF файлов со штрихкодами"""

    def __init__(self):
        """Инициализация процессора PDF"""
        self.temp_dir = None

    def extract_zip(self, zip_path: str) -> Path:
        """
        Распаковать ZIP архив с PDF файлами

        Args:
            zip_path: Путь к ZIP архиву

        Returns:
            Path: Путь к директории с распакованными файлами

        Raises:
            PDFProcessorError: При ошибке распаковки
        """
        try:
            zip_path = Path(zip_path)

            if not zip_path.exists():
                raise PDFProcessorError(f"ZIP файл не найден: {zip_path}")

            if not zipfile.is_zipfile(zip_path):
                raise PDFProcessorError(f"Файл не является ZIP архивом: {zip_path}")

            # Создаем временную директорию
            self.temp_dir = Path(tempfile.mkdtemp(prefix='ozon_barcodes_'))
            logger.info(f"Создана временная директория: {self.temp_dir}")

            # Распаковываем архив
            logger.info(f"Распаковка архива: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)

            # Подсчитываем количество PDF файлов
            pdf_files = list(self.temp_dir.glob('*.pdf'))
            logger.info(f"Распаковано PDF файлов: {len(pdf_files)}")

            return self.temp_dir

        except zipfile.BadZipFile as e:
            error_msg = f"Поврежденный ZIP архив: {str(e)}"
            logger.error(error_msg)
            raise PDFProcessorError(error_msg)

        except Exception as e:
            error_msg = f"Ошибка при распаковке ZIP: {str(e)}"
            logger.error(error_msg)
            raise PDFProcessorError(error_msg)

    def find_pdf_by_sku(self, sku: int, search_dir: Path) -> Optional[Path]:
        """
        Найти PDF файл по SKU

        Args:
            sku: SKU товара
            search_dir: Директория для поиска

        Returns:
            Path к PDF файлу или None если не найден
        """
        # Пробуем разные варианты имен файлов
        possible_names = [
            f"{sku}.pdf",
            f"OZN{sku}.pdf",
            f"{sku}_barcode.pdf"
        ]

        for name in possible_names:
            pdf_path = search_dir / name
            if pdf_path.exists():
                logger.debug(f"Найден PDF для SKU {sku}: {pdf_path.name}")
                return pdf_path

        # Если не нашли по точному совпадению, ищем файлы содержащие SKU в имени
        for pdf_file in search_dir.glob('*.pdf'):
            if str(sku) in pdf_file.stem:
                logger.debug(f"Найден PDF для SKU {sku} по частичному совпадению: {pdf_file.name}")
                return pdf_file

        logger.warning(f"Не найден PDF для SKU {sku}")
        return None

    def merge_pdfs(self, items: List[Dict], pdf_dir: Path, output_path: Path) -> Dict:
        """
        Объединить PDF файлы с учетом количества товаров

        Args:
            items: Список товаров с информацией о SKU и количестве
            pdf_dir: Директория с PDF файлами
            output_path: Путь к выходному PDF файлу

        Returns:
            Словарь со статистикой обработки

        Raises:
            PDFProcessorError: При ошибке обработки
        """
        try:
            logger.info("Начало объединения PDF файлов")

            output_pdf = PdfWriter()
            stats = {
                'total_items': len(items),
                'total_pages': 0,
                'processed_items': 0,
                'skipped_items': 0,
                'missing_pdfs': []
            }

            for item in items:
                sku = item.get('sku')
                quantity = item.get('quantity', 1)
                name = item.get('name', 'Неизвестный товар')

                logger.info(f"Обработка товара: SKU {sku}, количество: {quantity}")

                # Ищем PDF файл
                pdf_file = self.find_pdf_by_sku(sku, pdf_dir)

                if pdf_file is None:
                    logger.warning(f"Пропущен товар {sku} ({name}): PDF не найден")
                    stats['skipped_items'] += 1
                    stats['missing_pdfs'].append({
                        'sku': sku,
                        'name': name,
                        'quantity': quantity
                    })
                    continue

                # Читаем PDF файл
                try:
                    reader = PdfReader(pdf_file)

                    if len(reader.pages) == 0:
                        logger.warning(f"PDF файл {pdf_file.name} не содержит страниц")
                        stats['skipped_items'] += 1
                        continue

                    # Берем первую страницу (обычно штрихкод на первой странице)
                    page = reader.pages[0]

                    # Добавляем нужное количество копий
                    for i in range(quantity):
                        output_pdf.add_page(page)
                        stats['total_pages'] += 1

                    stats['processed_items'] += 1
                    logger.info(f"Добавлено {quantity} копий для SKU {sku}")

                except Exception as e:
                    logger.error(f"Ошибка при чтении PDF {pdf_file.name}: {str(e)}")
                    stats['skipped_items'] += 1
                    continue

            # Проверяем, что есть что сохранять
            if stats['total_pages'] == 0:
                raise PDFProcessorError("Нет страниц для сохранения. Проверьте наличие PDF файлов в архиве.")

            # Сохраняем итоговый PDF
            logger.info(f"Сохранение итогового PDF: {output_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'wb') as output_file:
                output_pdf.write(output_file)

            logger.info(f"Успешно создан PDF: {stats['total_pages']} страниц")
            logger.info(f"Обработано товаров: {stats['processed_items']}/{stats['total_items']}")

            if stats['skipped_items'] > 0:
                logger.warning(f"Пропущено товаров: {stats['skipped_items']}")

            return stats

        except PDFProcessorError:
            raise

        except Exception as e:
            error_msg = f"Ошибка при объединении PDF: {str(e)}"
            logger.error(error_msg)
            raise PDFProcessorError(error_msg)

    def cleanup(self):
        """Очистить временные файлы"""
        if self.temp_dir and self.temp_dir.exists():
            try:
                logger.info(f"Очистка временной директории: {self.temp_dir}")
                shutil.rmtree(self.temp_dir)
                logger.info("Временные файлы удалены")
            except Exception as e:
                logger.warning(f"Не удалось удалить временные файлы: {str(e)}")

    def print_pdf(self, pdf_path: Path, printer_name: Optional[str] = None) -> bool:
        """
        Отправить PDF на печать

        Args:
            pdf_path: Путь к PDF файлу
            printer_name: Имя принтера (если не указано, используется принтер по умолчанию)

        Returns:
            True если печать успешно отправлена, False иначе
        """
        try:
            system = platform.system()

            if system == 'Windows':
                return self._print_pdf_windows(pdf_path, printer_name)
            elif system == 'Darwin':  # macOS
                return self._print_pdf_macos(pdf_path, printer_name)
            elif system == 'Linux':
                return self._print_pdf_linux(pdf_path, printer_name)
            else:
                logger.error(f"Печать не поддерживается для платформы: {system}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при печати PDF: {str(e)}")
            return False

    def _print_pdf_windows(self, pdf_path: Path, printer_name: Optional[str]) -> bool:
        """Печать на Windows"""
        try:
            import win32api
            import win32print

            if printer_name is None:
                printer_name = win32print.GetDefaultPrinter()

            logger.info(f"Отправка на печать (Windows): {pdf_path} -> {printer_name}")

            win32api.ShellExecute(
                0,
                "print",
                str(pdf_path),
                f'/d:"{printer_name}"',
                ".",
                0
            )

            logger.info("Файл отправлен на печать")
            return True

        except ImportError:
            logger.error("Модуль pywin32 не установлен. Установите: pip install pywin32")
            return False
        except Exception as e:
            logger.error(f"Ошибка печати на Windows: {str(e)}")
            return False

    def _print_pdf_macos(self, pdf_path: Path, printer_name: Optional[str]) -> bool:
        """Печать на macOS"""
        try:
            import subprocess

            cmd = ['lpr']
            if printer_name:
                cmd.extend(['-P', printer_name])
            cmd.append(str(pdf_path))

            logger.info(f"Отправка на печать (macOS): {' '.join(cmd)}")

            subprocess.run(cmd, check=True)
            logger.info("Файл отправлен на печать")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка печати на macOS: {str(e)}")
            return False

    def _print_pdf_linux(self, pdf_path: Path, printer_name: Optional[str]) -> bool:
        """Печать на Linux"""
        try:
            import subprocess

            cmd = ['lp']
            if printer_name:
                cmd.extend(['-d', printer_name])
            cmd.append(str(pdf_path))

            logger.info(f"Отправка на печать (Linux): {' '.join(cmd)}")

            subprocess.run(cmd, check=True)
            logger.info("Файл отправлен на печать")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка печати на Linux: {str(e)}")
            return False

    def __enter__(self):
        """Контекстный менеджер: вход"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        self.cleanup()
