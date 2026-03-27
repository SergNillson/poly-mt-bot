"""
Paper Trader — копирует сделки трейде��а в бумажном режиме.
"""

import logging
from typing import Optional, Dict

from src.trading.position_manager import PositionManager
from src.database.database import Database
from src.polymarket.api_client import PolymarketAPIClient

logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Копирует сделки трейдера в paper trading режиме.
    """

    def __init__(
        self,
        position_manager: PositionManager,
        database: Database,
        api_client: PolymarketAPIClient,
        trader_address: str,
        copy_ratio: float = 1.0,
        max_position_size: float = 100.0
    ):
        self.position_manager = position_manager
        self.database = database
        self.api_client = api_client
        self.trader_address = trader_address.lower()
        self.copy_ratio = copy_ratio
        self.max_position_size = max_position_size
        logger.info(f"Инициализирован PaperTrader (копирование: {copy_ratio * 100}%, макс. позиция: ${max_position_size})")

    def should_copy_trade(self, trade_data: Dict) -> bool:
        """Проверяет, нужно ли копировать сделку."""
        return True

    def copy_buy(self, trade_data: Dict) -> Optional[int]:
        """
        Копирует покупку трейдера.
        
        Returns:
            ID открытой позиции или None
        """
        parsed_trade = trade_data['parsed_trade']
        market_title = trade_data['market_title']

        original_size = parsed_trade['size']
        copy_size = min(original_size * self.copy_ratio, self.max_position_size)

        position_id = self.position_manager.open_position(
            market_id=parsed_trade['market_id'],
            market_title=market_title,
            outcome=parsed_trade['outcome'],
            entry_price=parsed_trade['price'],
            size=copy_size,
            trader_tx_hash=parsed_trade.get('transaction_hash')
        )

        # ✅ ЛОГ: Открыта позиция
        logger.info(
            f"✅ [BUY] {market_title[:30]}... {parsed_trade['outcome']} @ ${parsed_trade['price']:.2f} | Size: ${copy_size:.2f} | PosID: {position_id}"
        )

        return position_id

    def copy_sell(self, trade_data: Dict) -> Optional[Dict]:
        """
        Копирует продажу трейдера — закрывает соответствующую позицию ПРОПОРЦИОНАЛЬНО.
        
        Логика:
        1. Получаем позицию трейдера ПОСЛЕ продажи
        2. Если позиция = 0 → закрываем полностью
        3. Если позиция > 0 → это была частичная продажа, НО мы всё равно закрываем полностью для простоты
        
        Returns:
            Данные закрытой позиции или None
        """
        parsed_trade = trade_data['parsed_trade']
        market_id = parsed_trade['market_id']
        outcome = parsed_trade['outcome']
        
        # ✅ Ищем открытую позицию
        position = self.database.get_open_position_by_market(market_id, outcome)
        
        if not position:
            logger.warning(f"⚠️  [SELL] Позиция не найдена: {parsed_trade['title'][:30]}... {outcome}")
            return None
        
        # ✅ Проверяем текущую позицию трейдера
        try:
            trader_positions = self.api_client.get_trader_positions(
                self.trader_address, 
                condition_id=market_id
            )
            
            # Находим позицию трейдера по outcome
            trader_position_size = 0
            for tp in trader_positions:
                if tp.get('outcome') == outcome:
                    trader_position_size = float(tp.get('size', 0))
                    break
            
            if trader_position_size == 0:
                # Трейдер полностью закрыл позицию
                logger.info(f"🔴 [SELL] Трейдер полностью закрыл позицию: {parsed_trade['title'][:30]}...")
                reason = 'sell_full'
            else:
                # Частичное закрытие (но мы закрываем полностью для простоты)
                logger.info(f"🟡 [SELL] Частичное закрытие трейдера (остаток: ${trader_position_size:.2f}), закрываем полностью")
                reason = 'sell_partial'
        
        except Exception as e:
            logger.error(f"Ошибка при получении позиций трейдера: {e}")
            reason = 'sell_error'
        
        # ✅ Закрываем позицию
        result = self.position_manager.close_position(
            position_id=position.id,
            exit_price=parsed_trade['price'],
            reason=reason
        )
        
        if result:
            logger.info(
                f"✅ [SELL] {result['market_title'][:30]}... {result['outcome']} | "
                f"Entry: ${result['entry_price']:.2f} → Exit: ${result['exit_price']:.2f} | "
                f"P&L: ${result['pnl']:.2f} ({result['pnl_percent']:.1f}%)"
            )
        
        return result

    def get_statistics(self) -> Dict:
        """Возвращает статистику торговли."""
        stats = {
            'open_positions': 0,
            'closed_positions': 0,
            'total_pnl': 0.0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0
        }
        
        # Открытые позиции
        open_positions = self.position_manager.get_open_positions()
        stats['open_positions'] = len(open_positions)
        
        # Закрытые позиции
        closed_positions = self.database.get_closed_positions()
        stats['closed_positions'] = len(closed_positions)
        
        # P&L
        for pos in closed_positions:
            if pos.pnl:
                stats['total_pnl'] += pos.pnl
                if pos.pnl > 0:
                    stats['winning_trades'] += 1
                else:
                    stats['losing_trades'] += 1
        
        # Win rate
        if stats['closed_positions'] > 0:
            stats['win_rate'] = (stats['winning_trades'] / stats['closed_positions']) * 100
        
        return stats