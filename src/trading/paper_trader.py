"""
Paper Trading - симуляция торговли без реальных денег.
Копирует сделки отслеживаемого трейдера в виртуальном режиме.
"""

import logging
from typing import Dict, Optional
from src.trading.position_manager import PositionManager
from src.database.database import Database
from src.polymarket.api_client import PolymarketAPIClient

logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Выполняет виртуальную торговлю (paper trading).
    Копирует сделки целевого трейдера без реальных денег.
    """
    
    def __init__(self, 
                 position_manager: PositionManager,
                 database: Database,
                 api_client: PolymarketAPIClient,
                 copy_ratio: float = 1.0,
                 max_position_size: float = 100.0):
        """
        Инициализация paper trader.
        
        Args:
            position_manager: Менеджер позиций
            database: База данных
            api_client: API клиент Polymarket
            copy_ratio: Коэффициент копирования (1.0 = 100%)
            max_position_size: Максимальный размер одной позиции в USD
        """
        self.position_manager = position_manager
        self.database = database
        self.api_client = api_client
        self.copy_ratio = copy_ratio
        self.max_position_size = max_position_size
        
        logger.info(f"Инициализирован PaperTrader (копирование: {copy_ratio*100}%, "
                   f"макс. позиция: ${max_position_size})")
    
    def copy_trade(self, trade_data: Dict) -> Optional[int]:
        """
        Копирует сделку целевого трейдера.
        
        Args:
            trade_data: Данные о сделке от TraderTracker
            
        Returns:
            ID открытой позиции или None
        """
        try:
            db_trade = trade_data['db_trade']
            parsed_trade = trade_data['parsed_trade']
            market_title = trade_data['market_title']
            
            # Рассчитываем размер позиции с учетом коэффициента копирования
            original_amount = parsed_trade['size']
            copy_amount = original_amount * self.copy_ratio
            
            # Ограничиваем максимальный размер позиции
            if copy_amount > self.max_position_size:
                logger.warning(f"Размер позиции ${copy_amount:.2f} превышает максимум "
                             f"${self.max_position_size:.2f}. Используется максимум.")
                copy_amount = self.max_position_size
            
            # Проверяем минимальный размер
            if copy_amount < 1.0:
                logger.warning(f"Размер позиции ${copy_amount:.2f} слишком мал. Пропускаем.")
                return None
            
            # Открываем позицию
            position_id = self.position_manager.open_position(
                market_id=parsed_trade['market_id'],
                market_title=market_title,
                outcome=parsed_trade['outcome'],
                amount=copy_amount,
                entry_price=parsed_trade['price'],
                tracked_trade_id=db_trade.id
            )
            
            if position_id:
                logger.info(f"🔄 Скопирована сделка трейдера")
                logger.info(f"   Оригинал: ${original_amount:.2f}")
                logger.info(f"   Копия: ${copy_amount:.2f} ({self.copy_ratio*100}%)")
            
            return position_id
            
        except Exception as e:
            logger.error(f"Ошибка при копировании сделки: {e}", exc_info=True)
            return None
    
    def should_copy_trade(self, trade_data: Dict) -> bool:
        """
        Определяет, нужно ли копировать данную сделку.
        Можно добавить фильтры (минимальный размер, определенные рынки и т.д.)
        
        Args:
            trade_data: Данные о сделке
            
        Returns:
            True если сделку нужно копировать
        """
        parsed_trade = trade_data['parsed_trade']
        
        # Проверка 1: Минимальный размер сделки
        min_trade_size = 10.0  # USD
        if parsed_trade['size'] < min_trade_size:
            logger.debug(f"Сделка слишком мала (${parsed_trade['size']:.2f} < ${min_trade_size})")
            return False
        
        # Проверка 2: Только покупки (не продажи)
        # Можно настроить в зависимости от стратегии
        if parsed_trade.get('side') == 'SELL':
            logger.debug("Пропускаем сделку на продажу")
            return False
        
        # Можно добавить больше проверок:
        # - Фильтр по определенным рынкам
        # - Ограничение на количество одновременно открытых позиций
        # - Фильтр по времени суток
        
        return True
    
    def get_statistics(self) -> Dict:
        """
        Возвращает статистику paper trading.
        
        Returns:
            Словарь со статистикой
        """
        pnl_stats = self.position_manager.get_total_pnl()
        open_positions = self.position_manager.get_open_positions()
        closed_positions = self.database.get_closed_positions()
        
        # Подсчитываем win rate
        profitable_trades = sum(1 for pos in closed_positions if pos.pnl and pos.pnl > 0)
        total_closed = len(closed_positions)
        win_rate = (profitable_trades / total_closed * 100) if total_closed > 0 else 0
        
        return {
            'realized_pnl': pnl_stats['realized_pnl'],
            'unrealized_pnl': pnl_stats['unrealized_pnl'],
            'total_pnl': pnl_stats['total_pnl'],
            'open_positions': len(open_positions),
            'closed_positions': total_closed,
            'win_rate': win_rate,
            'copy_ratio': self.copy_ratio,
            'max_position_size': self.max_position_size
        }
    
    def print_statistics(self):
        """
        Выводит красивую статистику в лог.
        """
        stats = self.get_statistics()
        
        logger.info("=" * 50)
        logger.info("📊 СТАТИСТИКА PAPER TRADING")
        logger.info("=" * 50)
        logger.info(f"Реализованный P&L:    ${stats['realized_pnl']:+.2f}")
        logger.info(f"Нереализованный P&L:  ${stats['unrealized_pnl']:+.2f}")
        logger.info(f"Общий P&L:            ${stats['total_pnl']:+.2f}")
        logger.info(f"-" * 50)
        logger.info(f"Открытых позиций:     {stats['open_positions']}")
        logger.info(f"Закрытых позиций:     {stats['closed_positions']}")
        logger.info(f"Win Rate:             {stats['win_rate']:.1f}%")
        logger.info(f"-" * 50)
        logger.info(f"Коэффициент копирования: {stats['copy_ratio']*100}%")
        logger.info(f"Макс. размер позиции:    ${stats['max_position_size']:.2f}")
        logger.info("=" * 50)