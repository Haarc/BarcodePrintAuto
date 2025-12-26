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

    def search_supply_orders(self, order_number: str) -> List[int]:
        """
        Поиск заявок на поставку по номеру заказа

        Args:
            order_number: Номер заказа (например, "2000038642317")

        Returns:
            Список ID заявок на поставку

        Raises:
            OzonAPIError: При ошибке получения данных
        """
        logger.info(f"Поиск заявок на поставку по номеру {order_number}")

        endpoint = '/v3/supply-order/list'
        data = {
            'filter': {
                'order_number_search': order_number,
                'states': ['READY_TO_SUPPLY']
            },
            'last_id': '',
            'limit': 100,
            'sort_by': 'ORDER_CREATION',
            'sort_dir': 'DESC'
        }

        try:
            result = self._make_request('POST', endpoint, data)

            # API возвращает order_ids напрямую, а не массив orders
            if 'order_ids' in result:
                # Прямой формат
                order_ids = result['order_ids']
            elif 'result' in result and 'order_ids' in result['result']:
                # Формат с result wrapper
                order_ids = result['result']['order_ids']
            else:
                logger.error(f"Неожиданный формат ответа API: {result}")
                raise OzonAPIError(f"Неверный формат ответа от API. Получены ключи: {list(result.keys())}")

            if not order_ids:
                logger.warning(f"Не найдено заявок на поставку с номером {order_number}")
                return []

            logger.info(f"Найдено {len(order_ids)} заявок на поставку: {order_ids}")

            return order_ids

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Неожиданная ошибка при поиске заявок: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def get_supply_order_details(self, order_ids: List[int]) -> List[Dict]:
        """
        Получить детальную информацию о заявках на поставку

        Args:
            order_ids: Список ID заявок на поставку

        Returns:
            Список заявок с полной информацией (bundle_ids, warehouse_ids и т.д.)

        Raises:
            OzonAPIError: При ошибке получения данных
        """
        logger.info(f"Получение информации о заявках: {order_ids}")

        endpoint = '/v3/supply-order/get'
        data = {'order_ids': order_ids}

        try:
            result = self._make_request('POST', endpoint, data)

            # Проверяем возможные форматы ответа
            if 'result' in result and 'orders' in result['result']:
                orders = result['result']['orders']
            elif 'orders' in result:
                orders = result['orders']
            else:
                logger.error(f"Неожиданный формат ответа API: {result}")
                raise OzonAPIError(f"Неверный формат ответа от API: отсутствует поле 'orders'. Получены ключи: {list(result.keys())}")

            logger.info(f"Получена информация о {len(orders)} заявках")

            return orders

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Неожиданная ошибка при получении информации о заявках: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def get_bundle_items(self, bundle_ids: List[str], dropoff_warehouse_id: int,
                        storage_warehouse_ids: List[int]) -> List[Dict]:
        """
        Получить состав поставки (список товаров)

        Args:
            bundle_ids: Список ID bundle
            dropoff_warehouse_id: ID склада отгрузки
            storage_warehouse_ids: Список ID складов хранения

        Returns:
            Список товаров с информацией о SKU, названии, количестве и т.д.

        Raises:
            OzonAPIError: При ошибке получения данных
        """
        logger.info(f"Получение состава поставки для bundle_ids: {bundle_ids}")

        endpoint = '/v1/supply-order/bundle'
        data = {
            'bundle_ids': bundle_ids,
            'is_asc': True,
            'item_tags_calculation': {
                'dropoff_warehouse_id': dropoff_warehouse_id,
                'storage_warehouse_ids': storage_warehouse_ids
            },
            'last_id': '',
            'limit': 100,
            'query': '',
            'sort_field': 'UNSPECIFIED'
        }

        try:
            result = self._make_request('POST', endpoint, data)

            # Проверяем возможные форматы ответа
            if 'result' in result and 'items' in result['result']:
                items = result['result']['items']
            elif 'items' in result:
                items = result['items']
            else:
                logger.error(f"Неожиданный формат ответа API: {result}")
                raise OzonAPIError(f"Неверный формат ответа от API: отсутствует поле 'items'. Получены ключи: {list(result.keys())}")

            logger.info(f"Получено {len(items)} уникальных товаров")

            # Подсчитываем общее количество товаров
            total_quantity = sum(item.get('quantity', 0) for item in items)
            logger.info(f"Всего товаров к печати: {total_quantity}")

            return items

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Неожиданная ошибка при получении состава поставки: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def get_supply_items_by_order_number(self, order_number: str) -> Dict:
        """
        Получить список товаров в поставке по номеру заказа (основной метод)

        Выполняет полный цикл запросов:
        1. Поиск заявок на поставку по номеру заказа
        2. Получение детальной информации о заявках
        3. Получение состава поставки (списка товаров)

        Args:
            order_number: Номер заказа (например, "2000038642317")

        Returns:
            Словарь с информацией о поставке:
            {
                'order_number': str,
                'order_ids': List[int],
                'items': List[Dict],
                'total_unique': int,
                'total_quantity': int
            }

        Raises:
            OzonAPIError: При ошибке получения данных
        """
        logger.info(f"Начало обработки заказа {order_number}")

        try:
            # Шаг 1: Поиск заявок на поставку
            order_ids = self.search_supply_orders(order_number)

            if not order_ids:
                raise OzonAPIError(f"Не найдено ни одной заявки на поставку с номером {order_number}")

            # Шаг 2: Получение детальной информации о заявках
            orders = self.get_supply_order_details(order_ids)

            if not orders:
                raise OzonAPIError(f"Не удалось получить информацию о заявках {order_ids}")

            # Извлекаем bundle_ids и warehouse информацию из первого заказа
            # (в большинстве случаев будет один заказ, но может быть несколько)
            all_items = []

            for order in orders:
                # Логируем полную структуру заказа для отладки
                logger.info(f"Структура заказа: {list(order.keys())}")

                # Проверяем наличие supplies
                if 'supplies' not in order or not order['supplies']:
                    logger.warning(f"В заказе {order.get('order_id')} отсутствует поле 'supplies'")
                    continue

                # Получаем warehouse информацию из заказа
                dropoff_warehouse_id = None
                if 'drop_off_warehouse' in order:
                    # Используем warehouse_id, а не id
                    dropoff_warehouse_id = order['drop_off_warehouse'].get('warehouse_id')

                # Обрабатываем каждую поставку в supplies
                for supply in order['supplies']:
                    # Извлекаем bundle_id из поставки
                    if 'bundle_id' not in supply:
                        logger.warning(f"В supply отсутствует bundle_id")
                        continue

                    bundle_id = supply['bundle_id']
                    bundle_ids = [bundle_id]  # API ожидает массив

                    # Получаем warehouse_id из storage_warehouse
                    storage_warehouse_ids = []
                    if 'storage_warehouse' in supply and 'warehouse_id' in supply['storage_warehouse']:
                        warehouse_id = supply['storage_warehouse']['warehouse_id']
                        storage_warehouse_ids = [warehouse_id]

                    # Проверка наличия необходимых данных
                    if not dropoff_warehouse_id:
                        logger.warning(f"Отсутствует dropoff_warehouse_id")
                        continue

                    if not storage_warehouse_ids:
                        logger.warning(f"Отсутствует storage_warehouse_id")
                        continue

                    logger.info(f"Обработка bundle_id: {bundle_id}")
                    logger.info(f"Dropoff warehouse: {dropoff_warehouse_id}")
                    logger.info(f"Storage warehouses: {storage_warehouse_ids}")

                    # Шаг 3: Получение состава поставки
                    items = self.get_bundle_items(bundle_ids, dropoff_warehouse_id, storage_warehouse_ids)
                    all_items.extend(items)

            if not all_items:
                raise OzonAPIError(f"Не удалось получить товары для заказа {order_number}")

            # Формируем итоговый результат
            total_unique = len(all_items)
            total_quantity = sum(item.get('quantity', 0) for item in all_items)

            result = {
                'order_number': order_number,
                'order_ids': order_ids,
                'items': all_items,
                'total_unique': total_unique,
                'total_quantity': total_quantity
            }

            logger.info(f"Обработка завершена: {total_unique} уникальных товаров, {total_quantity} штук всего")

            return result

        except OzonAPIError:
            raise
        except Exception as e:
            error_msg = f"Неожиданная ошибка при обработке заказа {order_number}: {str(e)}"
            logger.error(error_msg)
            raise OzonAPIError(error_msg)

    def validate_credentials(self) -> bool:
        """
        Проверить корректность API credentials

        Returns:
            True если credentials корректны, False иначе
        """
        try:
            # Пробуем получить список поставок для проверки
            endpoint = '/v3/supply-order/list'
            data = {
                'filter': {
                    'states': ['READY_TO_SUPPLY']
                },
                'last_id': '',
                'limit': 1,
                'sort_by': 'ORDER_CREATION',
                'sort_dir': 'DESC'
            }

            self._make_request('POST', endpoint, data)
            logger.info("API credentials валидны")
            return True

        except OzonAPIError as e:
            logger.error(f"Некорректные API credentials: {str(e)}")
            return False
