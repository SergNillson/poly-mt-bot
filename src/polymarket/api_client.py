"""
Клиент для работы с Polymarket API.
Получает данные о рынках, сделках трейдеров и текущих ценах.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__) 


class PolymarketAPIClient:
    """
    Класс для взаимодействия с Polymarket API.
    """
    
    # API endpoints
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_API = "https://gamma-api.polymarket.com"
    DATA_API = "https://data-api.polymarket.com"
    
    def __init__(self):
        """Инициализация API клиента."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        logger.info("PolymarketAPIClient инициализирован")
    
    def get_trader_trades(self, trader_address: str, limit: int = 100) -> List[Dict]:
        """
        Получает последние активности трейдера (trades, positions, resolves).
        
        Args:
            trader_address: Адрес кошелька трейдера
            limit: Максимальное количество активностей
            
        Returns:
            Список активностей трейдера
        """
        try:
            # ✅ Используем /activity вместо /trades
            url = f"{self.DATA_API}/activity"
            params = {
                'user': trader_address.lower(),
                'limit': limit,
                'sortBy': 'TIMESTAMP',
                'sortDirection': 'DESC'
            }
            
            logger.debug(f"Запрос: {url} с параметрами {params}")
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            activities = response.json()
            
            logger.info(f"✅ Получено {len(activities)} активностей для {trader_address[:10]}...")
            return activities
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении активностей: {e}")
            return []
    
    def get_trader_positions(self, trader_address: str, condition_id: str = None) -> List[Dict]:
        """
        Получает текущие позиции трейдера.
        
        Args:
            trader_address: Адрес кошелька трейдера
            condition_id: ID рынка (опционально, для фильтрации)
            
        Returns:
            Список позиций трейдера
        """
        try:
            url = f"{self.GAMMA_API}/positions"
            params = {'user': trader_address.lower()}
            
            if condition_id:
                params['conditionId'] = condition_id
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            positions = response.json()
            logger.debug(f"Получено {len(positions)} позиций для {trader_address[:8]}...")
            return positions
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении позиций: {e}")
            return []
    
    def get_market_info(self, market_id: str) -> Optional[Dict]:
        """
        Получает информацию о рынке.
        
        Args:
            market_id: ID рынка (conditionId)
            
        Returns:
            Информация о рынке или None
        """
        try:
            url = f"{self.GAMMA_API}/markets/{market_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            market_data = response.json()
            logger.debug(f"Получена информация о рынке {market_id}")
            return market_data
            
        except requests.exceptions.RequestException:
            return None
    
    def get_current_price(self, token_id: str) -> Optional[float]:
        """
        Получает текущую цену токена (YES или NO).
        
        Args:
            token_id: ID токена
            
        Returns:
            Текущая цена или None
        """
        try:
            url = f"{self.BASE_URL}/price"
            params = {'token_id': token_id}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            price_data = response.json()
            price = float(price_data.get('price', 0))
            
            logger.debug(f"Текущая цена токена {token_id[:8]}...: {price}")
            return price
            
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"Ошибка при получении цены: {e}")
            return None
    
    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        Получает стакан ордеров для токена.
        
        Args:
            token_id: ID токена
            
        Returns:
            Данные стакана (bids, asks) или None
        """
        try:
            url = f"{self.BASE_URL}/book"
            params = {'token_id': token_id}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            orderbook = response.json()
            logger.debug(f"Получен стакан для токена {token_id[:8]}...")
            return orderbook
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении стакана: {e}")
            return None
    
    def get_active_markets(self, limit: int = 50) -> List[Dict]:
        """
        Получает список активных рынков.
        
        Args:
            limit: Максимальное количество рынков
            
        Returns:
            Список активных рынков
        """
        try:
            url = f"{self.GAMMA_API}/markets"
            params = {
                'active': True,
                'limit': limit
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            markets = response.json()
            logger.info(f"Получено {len(markets)} активных рынков")
            return markets
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении активных рынков: {e}")
            return []
    
    def parse_trade_data(self, activity: Dict) -> Dict:
        """
        Парсит сырые данные активности в удобный формат.
        
        Args:
            activity: Сырые данные активности от API (/activity endpoint)
            
        Returns:
            Обработанные данные активности
        """
        activity_type = activity.get('type', 'TRADE')
        
        # ✅ Для POSITION_CLOSE определяем side как SELL
        side = activity.get('side')
        if activity_type == 'POSITION_CLOSE' and not side:
            side = 'SELL'
        
        # ✅ ИСПРАВЛЕНО: Парсим timestamp с UTC timezone
        timestamp_raw = activity.get('timestamp', 0)
        timestamp = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
        
        return {
            'timestamp': timestamp,
            'market_id': activity.get('conditionId'),
            'outcome': activity.get('outcome'),
            'size': float(activity.get('size', 0)),
            'price': float(activity.get('price', 0)),
            'transaction_hash': activity.get('transactionHash'),
            'maker': activity.get('proxyWallet'),
            'side': side,
            'asset': activity.get('asset'),
            'title': activity.get('title', 'Unknown Market'),
            'slug': activity.get('slug', ''),
            'type': activity_type,
            'usdc_size': float(activity.get('usdcSize', 0)),
        }
    
    def is_new_trade(self, trade: Dict, last_check_time: datetime) -> bool:
        """
        Проверяет, является ли сделка новой (после последней проверки).
        
        Args:
            trade: Данные сделки
            last_check_time: Время последней проверки
            
        Returns:
            True если сделка новая
        """
        trade_time = datetime.fromtimestamp(trade.get('timestamp', 0), tz=timezone.utc)
        return trade_time > last_check_time