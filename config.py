"""
Модуль конфигурации для приложения автоматизации печати штрихкодов Ozon
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


class Config:
    """Класс конфигурации приложения"""

    # Ozon API настройки
    OZON_CLIENT_ID = os.getenv('OZON_CLIENT_ID', '')
    OZON_API_KEY = os.getenv('OZON_API_KEY', '')
    OZON_API_URL = 'https://api-seller.ozon.ru'

    # Директории
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', './output'))
    LOGS_DIR = Path(os.getenv('LOGS_DIR', './logs'))

    # Принтер
    DEFAULT_PRINTER = os.getenv('DEFAULT_PRINTER', '')

    # Создание директорий, если их нет
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    @classmethod
    def validate(cls):
        """Валидация конфигурации"""
        errors = []

        if not cls.OZON_CLIENT_ID:
            errors.append("OZON_CLIENT_ID не указан в .env файле")

        if not cls.OZON_API_KEY:
            errors.append("OZON_API_KEY не указан в .env файле")

        return errors

    @classmethod
    def get_log_filepath(cls):
        """Получить путь к файлу логов"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        return cls.LOGS_DIR / f'ozon_automation_{date_str}.log'

    @classmethod
    def get_output_filepath(cls, supply_id, suffix='полная'):
        """Получить путь к выходному PDF файлу"""
        return cls.OUTPUT_DIR / f'Поставка_{supply_id}_{suffix}.pdf'


def setup_logging():
    """Настройка логирования"""
    log_filepath = Config.get_log_filepath()

    # Создаем форматтер
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Настраиваем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Удаляем существующие обработчики
    logger.handlers.clear()

    # Файловый обработчик
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Инициализация логирования при импорте модуля
logger = setup_logging()
