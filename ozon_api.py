"""
Модуль для работы с Ozon API
"""
import requests
import logging
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)


class OzonAPIError(Exception):
    """Исключение для ошибок Ozon API"""
    pass


class OzonAPI:
    """Класс для работы с Ozon Seller API"""

    def __init__(self, client_id: Optional[str] = None, api_key: Optional[str] = None):
        """
        Инициализация клиента Ozon API

        Args:
            client_id: Client-Id для API (если не указан, берется из конфига)
            api_key: API-Key для API (если не указан, берется из конфига)
        """
        self.client_id = client_id or Config.OZON_CLIENT_ID
        self.api_key = api_key or Config.OZON_API_KEY
        self.base_url = Config.OZON_API_URL

        if not self.client_id or not self.api_key:
            raise OzonAPIError("Client-Id и API-Key должны быть указаны")

    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для API запросов"""
        return {
            'Client-Id': self.client_id,
            'Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Выполнить запрос к API

        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Endpoint API
            data: Данные для отправки

        Returns:
            Ответ от API в виде словаря

        Raises:
            OzonAPIError: При ошибке запроса
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            logger.info(f"Запрос к API: {method} {url}")

            if method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method.upper() == 'GET':
                response = requests.get(url, params=data, headers=headers, timeout=30)
            else:
                raise OzonAPIError(f"Неподдерживаемый HTTP метод: {method}")

            response.raise_for_status()
            result = response.json()

            logger.info(f"Успешный ответ от API: {response.status_code}")
            return result

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP ошибка: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text}"

            logger.error(error_msg)
            raise OzonAPIError(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"Ошибка запроса к API: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

        except ValueError as e:
            error_msg = f"Ошибка парсинга JSON ответа: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def get_supply_bundle(self, supply_id: int) -> Dict:
        """
        Получить данные о поставке

        Args:
            supply_id: ID поставки

        Returns:
            Словарь с данными о поставке

        Raises:
            OzonAPIError: При ошибке получения данных
        """
        logger.info(f"Получение данных поставки {supply_id}")

        endpoint = '/v1/supply-order/bundle'
        data = {'supply_id': supply_id}

        try:
            result = self._make_request('POST', endpoint, data)

            if 'result' not in result:
                raise OzonAPIError("Неверный формат ответа от API")

            return result['result']

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Неожиданная ошибка при получении данных поставки: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def get_supply_items(self, supply_id: int) -> List[Dict]:
        """
        Получить список товаров в поставке

        Args:
            supply_id: ID поставки

        Returns:
            Список товаров с информацией о SKU, штрихкоде, названии и количестве

        Raises:
            OzonAPIError: При ошибке получения данных
        """
        try:
            bundle_data = self.get_supply_bundle(supply_id)

            if 'items' not in bundle_data:
                raise OzonAPIError("В ответе API отсутствует список товаров")

            items = bundle_data['items']
            logger.info(f"Получено {len(items)} уникальных товаров в поставке")

            # Подсчитываем общее количество товаров
            total_quantity = sum(item.get('quantity', 0) for item in items)
            logger.info(f"Всего товаров к печати: {total_quantity}")

            return items

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Ошибка при обработке списка товаров: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def get_supply_statistics(self, supply_id: int) -> Dict:
        """
        Получить статистику по поставке

        Args:
            supply_id: ID поставки

        Returns:
            Словарь со статистикой поставки
        """
        try:
            items = self.get_supply_items(supply_id)

            total_unique = len(items)
            total_quantity = sum(item.get('quantity', 0) for item in items)

            stats = {
                'supply_id': supply_id,
                'unique_items': total_unique,
                'total_quantity': total_quantity,
                'items': items
            }

            logger.info(f"Статистика поставки {supply_id}: "
                       f"{total_unique} уникальных товаров, "
                       f"{total_quantity} штук всего")

            return stats

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Ошибка при получении статистики: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def validate_credentials(self) -> bool:
        """
        Проверить корректность API credentials

        Returns:
            True если credentials корректны, False иначе
        """
        try:
            # Пробуем получить список поставок (любой endpoint для проверки)
            endpoint = '/v1/supply-order/list'
            data = {
                'dir': 'ASC',
                'filter': {},
                'limit': 1,
                'offset': 0
            }

            self._make_request('POST', endpoint, data)
            logger.info("API credentials валидны")
            return True

        except OzonAPIError as e:
            logger.error(f"Некорректные API credentials: {str(e)}")
            return False
