"""
Модуль для управления торговыми позициями.
Отвечает за открытие, закрытие позиций и расчет P&L.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from src.database.database import Database
from src.polymarket.api_client import PolymarketAPIClient

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Управляет торговыми позициями: открытие, закрытие, расчет прибыли/убытка.
    """
    
    def __init__(self, database: Database, api_client: PolymarketAPIClient):
        """
        Инициализация менеджера позиций.
        
        Args:
            database: База данных для хранения позиций
            api_client: API клиент для получения текущих цен
        """
        self.database = database
        self.api_client = api_client
        logger.info("Инициализирован PositionManager")
    
    def open_position(self, 
                     market_id: str,
                     market_title: str,
                     outcome: str,
                     amount: float,
                     entry_price: float,
                     tracked_trade_id: int) -> Optional[int]:
        """
        Открывает новую позицию.
        
        Args:
            market_id: ID рынка
            market_title: Название рынка
            outcome: YES или NO
            amount: Размер позиции в USD
            entry_price: Цена входа
            tracked_trade_id: ID сделки трейдера, которую копируем
            
        Returns:
            ID созданной позиции или None при ошибке
        """
        try:
            position_id = self.database.add_position(
                market_id=market_id,
                market_title=market_title,
                outcome=outcome,
                amount=amount,
                entry_price=entry_price,
                tracked_trade_id=tracked_trade_id
            )
            
            logger.info(f"✅ Открыта позиция #{position_id}")
            logger.info(f"   Рынок: {market_title}")
            logger.info(f"   {outcome} @ ${entry_price:.3f}")
            logger.info(f"   Размер: ${amount:.2f}")
            
            return position_id
            
        except Exception as e:
            logger.error(f"Ошибка при открытии позиции: {e}", exc_info=True)
            return None
    
    def close_position(self, position_id: int, exit_price: float, reason: str = "manual") -> bool:
        """
        Закрывает позицию.
        
        Args:
            position_id: ID позиции
            exit_price: Цена закрытия
            reason: Причина закрытия (manual, stop_loss, take_profit, market_closed)
            
        Returns:
            True если позиция успешно закрыта
        """
        try:
            position = self.database.get_position(position_id)
            if not position:
                logger.error(f"Позиция #{position_id} не найдена")
                return False
            
            if position.status != "open":
                logger.warning(f"Позиция #{position_id} уже закрыта")
                return False
            
            # Рассчитываем P&L
            pnl = self.calculate_pnl(position.amount, position.entry_price, exit_price)
            
            # Закрываем позицию в БД
            success = self.database.close_position(
                position_id=position_id,
                exit_price=exit_price,
                pnl=pnl
            )
            
            if success:
                pnl_sign = "📈" if pnl >= 0 else "📉"
                logger.info(f"{pnl_sign} Закрыта позиция #{position_id}")
                logger.info(f"   Рынок: {position.market_title}")
                logger.info(f"   Вход: ${position.entry_price:.3f} → Выход: ${exit_price:.3f}")
                logger.info(f"   P&L: ${pnl:+.2f}")
                logger.info(f"   Причина: {reason}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии позиции: {e}", exc_info=True)
            return False
    
    def calculate_pnl(self, amount: float, entry_price: float, exit_price: float) -> float:
        """
        Рассчитывает прибыль/убыток позиции.
        
        Args:
            amount: Размер позиции в USD
            entry_price: Цена входа
            exit_price: Цена выхода
            
        Returns:
            P&L в USD
        """
        # Количество контрактов = amount / entry_price
        contracts = amount / entry_price
        
        # P&L = contracts * (exit_price - entry_price)
        pnl = contracts * (exit_price - entry_price)
        
        return pnl
    
    def get_open_positions(self) -> List:
        """
        Получает все открытые позиции.
        
        Returns:
            Список открытых позиций
        """
        return self.database.get_open_positions()
    
    def get_position_current_price(self, position) -> Optional[float]:
        """
        Получает текущую цену для позиции.
        
        Args:
            position: Объект позиции из БД
            
        Returns:
            Текущая цена или None
        """
        # Здесь нужно получить token_id из market_id и outcome
        # Это зависит от структуры API Polymarket
        # Упрощенная версия:
        try:
            market_info = self.api_client.get_market_info(position.market_id)
            if not market_info:
                return None
            
            # Ищем токен для нужного outcome
            tokens = market_info.get('tokens', [])
            for token in tokens:
                if token.get('outcome') == position.outcome:
                    token_id = token.get('token_id')
                    return self.api_client.get_current_price(token_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении текущей цены: {e}")
            return None
    
    def update_positions_with_current_prices(self):
        """
        Обновляет текущие цены и нереализованный P&L для всех открытых позиций.
        """
        open_positions = self.get_open_positions()
        
        for position in open_positions:
            current_price = self.get_position_current_price(position)
            
            if current_price:
                unrealized_pnl = self.calculate_pnl(
                    position.amount,
                    position.entry_price,
                    current_price
                )
                
                logger.debug(f"Позиция #{position.id}: текущая цена ${current_price:.3f}, "
                           f"нереализованный P&L: ${unrealized_pnl:+.2f}")
    
    def get_total_pnl(self) -> Dict[str, float]:
        """
        Возвращает общую статистику по P&L.
        
        Returns:
            Словарь с realized_pnl и unrealized_pnl
        """
        # Реализованный P&L (закрытые позиции)
        closed_positions = self.database.get_closed_positions()
        realized_pnl = sum(pos.pnl for pos in closed_positions if pos.pnl)
        
        # Нереализованный P&L (открытые позиции)
        open_positions = self.get_open_positions()
        unrealized_pnl = 0.0
        
        for position in open_positions:
            current_price = self.get_position_current_price(position)
            if current_price:
                unrealized_pnl += self.calculate_pnl(
                    position.amount,
                    position.entry_price,
                    current_price
                )
        
        return {
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': realized_pnl + unrealized_pnl
        }