"""
Paper Trader — копирует сделки трейдера в бумажном режиме.
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
        1. Получаем позицию трейдера ДО продажи
        2. Вычисляем процент продажи: (размер_продажи / размер_позиции_трейдера)
        3. Продаём тот же процент СВОЕЙ позиции
        
        Returns:
            Данные закрытой позиции или None
        """
        parsed_trade = trade_data['parsed_trade']
        
        logger.info(f"🔍 Обрабатываю SELL: market={parsed_trade['market_id'][:8]}... outcome={parsed_trade['outcome']} size=${parsed_trade['size']:.2f}")
        
        # Находим СВОЮ открытую позицию
        my_position = self.position_manager.get_position_by_market(
            market_id=parsed_trade['market_id'],
            outcome=parsed_trade['outcome']
        )

        if not my_position:
            logger.warning(f"⚠️  Своя позиция НЕ найдена для закрытия! market={parsed_trade['market_id'][:8]}... outcome={parsed_trade['outcome']}")
            return None

        logger.info(f"   └─ Найдена своя позиция ID={my_position.id} | Size: {my_position.amount:.2f}")

        # Получаем ТЕКУЩУЮ позицию трейдера (после продажи)
        trader_positions = self.api_client.get_trader_positions(
            trader_address=self.trader_address,
            condition_id=parsed_trade['market_id']
        )

        # Фильтруем по outcome
        trader_position = None
        for pos in trader_positions:
            if pos.get('outcome') == parsed_trade['outcome']:
                trader_position = pos
                break

        if not trader_position:
            # Трейдер полностью закрыл позицию — закрываем и мы полностью
            logger.info(f"   └─ Трейдер полностью закрыл позицию → закрываю всю свою позицию")
            close_size = my_position.amount
            close_percentage = 100.0
        else:
            # Трейдер закрыл частично — вычисляем процент
            trader_current_size = float(trader_position.get('size', 0))
            
            # Размер позиции трейдера ДО продажи = текущий + проданный
            trader_size_before = trader_current_size + parsed_trade['size']
            
            # Процент продажи
            sell_percentage = (parsed_trade['size'] / trader_size_before) if trader_size_before > 0 else 1.0
            
            # Закрываем тот же процент СВОЕЙ позиции
            close_size = my_position.amount * sell_percentage
            close_percentage = sell_percentage * 100
            
            logger.info(f"   └─ Трейдер продал {sell_percentage*100:.1f}% позиции → закрываю {close_percentage:.1f}% своей")

        # Закрываем позицию (полностью или частично)
        if close_percentage >= 99:  # Если закрываем почти всё (>99%) — закрываем полностью
            closed_position = self.position_manager.close_position(
                position_id=my_position.id,
                exit_price=parsed_trade['price'],
                reason="trader_sell"
            )

            if closed_position:
                pnl = closed_position['pnl']
                pnl_sign = "+" if pnl > 0 else ""
                logger.info(
                    f"🔻 [SELL 100%] {closed_position['market_title'][:30]}... {closed_position['outcome']} @ ${closed_position['exit_price']:.2f} | "
                    f"P&L: {pnl_sign}${pnl:.2f} ({pnl_sign}{closed_position['pnl_percent']:.1f}%)"
                )
            return closed_position
        else:
            # Частичное закрытие — уменьшаем размер позиции
            new_size = my_position.amount - close_size
            
            # Рассчитываем частичный P&L
            partial_pnl = (parsed_trade['price'] - my_position.entry_price) * close_size
            partial_pnl_percent = ((parsed_trade['price'] - my_position.entry_price) / my_position.entry_price) * 100
            
            # Обновляем размер позиции в БД
            self.position_manager.update_position_size(my_position.id, new_size)
            
            logger.info(
                f"🔻 [SELL {close_percentage:.1f}%] {my_position.market_title[:30]}... {my_position.outcome} @ ${parsed_trade['price']:.2f} | "
                f"Закрыто: ${close_size:.2f} | Осталось: ${new_size:.2f} | "
                f"P&L: {'+' if partial_pnl > 0 else ''}${partial_pnl:.2f} ({'+' if partial_pnl_percent > 0 else ''}{partial_pnl_percent:.1f}%)"
            )
            
            return {
                'position_id': my_position.id,
                'market_title': my_position.market_title,
                'outcome': my_position.outcome,
                'entry_price': my_position.entry_price,
                'exit_price': parsed_trade['price'],
                'size': close_size,
                'pnl': partial_pnl,
                'pnl_percent': partial_pnl_percent,
                'reason': 'partial_sell',
                'remaining_size': new_size
            }

    def get_statistics(self) -> Dict:
        """Получает статистику."""
        return self.position_manager.get_statistics()