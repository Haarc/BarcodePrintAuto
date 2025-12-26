"""
Главный скрипт для автоматизации печати штрихкодов Ozon FBO
"""
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from config import Config, logger
from ozon_api import OzonAPI, OzonAPIError
from pdf_processor import PDFProcessor, PDFProcessorError


def process_supply(
    order_number: str,
    zip_path: str,
    auto_print: bool = False,
    printer_name: Optional[str] = None
) -> bool:
    """
    Обработать заказ: получить данные из API и создать PDF

    Args:
        order_number: Номер заказа (например, "2000038642317")
        zip_path: Путь к ZIP архиву со штрихкодами
        auto_print: Автоматически отправить на печать
        printer_name: Имя принтера (опционально)

    Returns:
        True если обработка успешна, False иначе
    """
    try:
        logger.info(f"Начало обработки заказа {order_number}")

        # Инициализация API клиента
        logger.info("Подключение к Ozon API...")
        api = OzonAPI()

        # Получение данных о заказе (полный цикл: list -> get -> bundle)
        logger.info(f"Получение данных о заказе {order_number}...")
        supply_data = api.get_supply_items_by_order_number(order_number)

        if not supply_data or not supply_data.get('items'):
            logger.error("Заказ не содержит товаров")
            return False

        items = supply_data['items']

        # Вывод статистики
        print_statistics(supply_data)

        # Обработка PDF
        with PDFProcessor() as processor:
            # Распаковка ZIP архива
            logger.info("Распаковка ZIP архива...")
            pdf_dir = processor.extract_zip(zip_path)

            # Объединение PDF файлов
            output_path = Config.get_output_filepath(order_number)
            logger.info("Объединение PDF файлов...")

            merge_stats = processor.merge_pdfs(items, pdf_dir, output_path)

            # Вывод результатов
            print_merge_results(merge_stats, output_path)

            # Печать, если требуется
            if auto_print:
                logger.info("Отправка на печать...")
                printer = printer_name or Config.DEFAULT_PRINTER
                if processor.print_pdf(output_path, printer):
                    logger.info("✓ Файл успешно отправлен на печать")
                else:
                    logger.warning("✗ Не удалось отправить файл на печать")

        logger.info("Обработка завершена успешно")
        return True

    except OzonAPIError as e:
        logger.error(f"Ошибка API: {str(e)}")
        return False

    except PDFProcessorError as e:
        logger.error(f"Ошибка обработки PDF: {str(e)}")
        return False

    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
        return False


def print_statistics(supply_data: dict):
    """Вывести статистику заказа"""
    print("\n" + "=" * 60)
    print(f"СТАТИСТИКА ЗАКАЗА {supply_data['order_number']}")
    print("=" * 60)
    print(f"ID заявок: {supply_data['order_ids']}")
    print(f"Уникальных товаров: {supply_data['total_unique']}")
    print(f"Всего к печати: {supply_data['total_quantity']} штук")
    print("\nСостав заказа:")
    print("-" * 60)

    for i, item in enumerate(supply_data['items'], 1):
        sku = item.get('sku', 'N/A')
        offer_id = item.get('offer_id', 'N/A')
        name = item.get('name', 'Неизвестный товар')
        quantity = item.get('quantity', 0)

        # Обрезаем длинное название
        if len(name) > 50:
            name = name[:47] + "..."

        print(f"{i:2d}. SKU {sku:<10} - {name:<50} ({quantity} шт)")

    print("=" * 60 + "\n")


def print_merge_results(stats: dict, output_path: Path):
    """Вывести результаты объединения PDF"""
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ОБРАБОТКИ")
    print("=" * 60)
    print(f"Обработано товаров: {stats['processed_items']}/{stats['total_items']}")
    print(f"Создано страниц: {stats['total_pages']}")

    if stats['skipped_items'] > 0:
        print(f"\n⚠ Пропущено товаров: {stats['skipped_items']}")

        if stats['missing_pdfs']:
            print("\nТовары без PDF файлов:")
            for item in stats['missing_pdfs']:
                sku = item['sku']
                name = item['name']
                quantity = item['quantity']
                if len(name) > 50:
                    name = name[:47] + "..."
                print(f"  - SKU {sku}: {name} ({quantity} шт)")

    print(f"\n✓ Создан файл: {output_path}")
    print(f"  Размер: {output_path.stat().st_size / 1024:.1f} KB")
    print("=" * 60 + "\n")


def interactive_mode():
    """Интерактивный режим работы"""
    print("\n" + "=" * 60)
    print("АВТОМАТИЗАЦИЯ ПЕЧАТИ ШТРИХКОДОВ OZON FBO")
    print("=" * 60 + "\n")

    # Проверка конфигурации
    errors = Config.validate()
    if errors:
        print("✗ Ошибки конфигурации:")
        for error in errors:
            print(f"  - {error}")
        print("\nНастройте .env файл и повторите попытку.")
        return False

    # Ввод данных
    try:
        order_number = input("Введите номер заказа (например, 2000038642317): ").strip()
        if not order_number:
            print("✗ Номер заказа не может быть пустым")
            return False

        zip_path = input("Укажите путь к ZIP архиву: ").strip()
        if not Path(zip_path).exists():
            print(f"✗ Файл не найден: {zip_path}")
            return False

        auto_print = input("Печатать автоматически? (y/n): ").strip().lower() == 'y'

        printer_name = None
        if auto_print:
            printer = input(f"Имя принтера (Enter для '{Config.DEFAULT_PRINTER}'): ").strip()
            if printer:
                printer_name = printer

        # Обработка
        return process_supply(order_number, zip_path, auto_print, printer_name)

    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        return False

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        return False


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='Автоматизация печати штрихкодов для поставок Ozon FBO',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  Интерактивный режим:
    python main.py

  С параметрами:
    python main.py --order-number 2000038642317 --zip-path barcode.zip

  С автоматической печатью:
    python main.py --order-number 2000038642317 --zip-path barcode.zip --print

  Указать принтер:
    python main.py --order-number 2000038642317 --zip-path barcode.zip --print --printer "Мой принтер"
        """
    )

    parser.add_argument(
        '--order-number',
        type=str,
        help='Номер заказа Ozon (например, 2000038642317)'
    )

    parser.add_argument(
        '--zip-path',
        type=str,
        help='Путь к ZIP архиву со штрихкодами'
    )

    parser.add_argument(
        '--print',
        action='store_true',
        help='Автоматически отправить на печать'
    )

    parser.add_argument(
        '--printer',
        type=str,
        help='Имя принтера для печати'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Проверить конфигурацию и API credentials'
    )

    args = parser.parse_args()

    # Валидация конфигурации
    if args.validate:
        print("Проверка конфигурации...")
        errors = Config.validate()

        if errors:
            print("✗ Ошибки конфигурации:")
            for error in errors:
                print(f"  - {error}")
            return 1

        print("✓ Конфигурация корректна")

        print("\nПроверка API credentials...")
        try:
            api = OzonAPI()
            if api.validate_credentials():
                print("✓ API credentials корректны")
                return 0
            else:
                print("✗ Некорректные API credentials")
                return 1
        except Exception as e:
            print(f"✗ Ошибка проверки API: {str(e)}")
            return 1

    # Режим с параметрами
    if args.order_number and args.zip_path:
        success = process_supply(
            args.order_number,
            args.zip_path,
            args.print,
            args.printer
        )
        return 0 if success else 1

    # Интерактивный режим
    if not args.order_number and not args.zip_path:
        success = interactive_mode()
        return 0 if success else 1

    # Неполные параметры
    parser.print_help()
    print("\n✗ Ошибка: Укажите либо оба параметра (--order-number и --zip-path), либо запустите без параметров для интерактивного режима")
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        sys.exit(1)
