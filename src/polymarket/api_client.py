"""
Клиент для работы с Polymarket API.
Получает данные о рынках, сделках трейдеров и текущих ценах.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__) 


class PolymarketAPIClient:
    """
    Класс для взаимодействия с Polymarket API.
    """
    
    # API endpoints
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_API = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        """Инициализация API клиента."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_trader_trades(self, trader_address: str, limit: int = 100) -> List[Dict]:
        """
        Получает последние сделки трейдера.
        
        Args:
            trader_address: Адрес кошелька трейдера
            limit: Максимальное количество сделок
            
        Returns:
            Список сделок трейдера
        """
        try:
            url = f"{self.GAMMA_API}/events"
            params = {
                'maker': trader_address,
                'limit': limit
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            trades = response.json()
            logger.info(f"Получено {len(trades)} сделок для трейдера {trader_address[:8]}...")
            return trades
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении сделок: {e}")
            return []
    
    def get_market_info(self, market_id: str) -> Optional[Dict]:
        """
        Получает информацию о рынке.
        
        Args:
            market_id: ID рынка
            
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
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении информации о рынке: {e}")
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
    
    def parse_trade_data(self, trade: Dict) -> Dict:
        """
        Парсит сырые данные сделки в удобный формат.
        
        Args:
            trade: Сырые данные сделки от API
            
        Returns:
            Обработанные данные сделки
        """
        return {
            'timestamp': datetime.fromtimestamp(trade.get('timestamp', 0)),
            'market_id': trade.get('market'),
            'outcome': trade.get('outcome'),  # YES или NO
            'size': float(trade.get('size', 0)),
            'price': float(trade.get('price', 0)),
            'transaction_hash': trade.get('transaction_hash'),
            'maker': trade.get('maker'),
            'side': trade.get('side')  # BUY или SELL
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
        trade_time = datetime.fromtimestamp(trade.get('timestamp', 0))
        return trade_time > last_check_time
        
