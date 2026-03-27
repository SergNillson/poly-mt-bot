"""
Управление позициями в paper trading режиме.
Хранение, обновление и расчёт P&L для открытых позиций.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime

from src.database.database import Database
from src.polymarket.api_client import PolymarketAPIClient

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Управляет бумажными позициями (paper trading).
    """

    def __init__(self, database: Database, api_client: PolymarketAPIClient):
        self.database = database
        self.api_client = api_client
        logger.info("Инициализирован PositionManager")

    def open_position(
        self,
        market_id: str,
        market_title: str,
        outcome: str,
        entry_price: float,
        size: float,
        trader_tx_hash: Optional[str] = None
    ) -> int:
        """
        Открывает новую позицию.
        """
        position_id = self.database.add_position(
            market_id=market_id,
            market_title=market_title,
            outcome=outcome,
            amount=size,
            entry_price=entry_price
        )
        
        logger.debug(f"Открыта позиция ID={position_id}: {market_id[:8]}... {outcome}")
        
        return position_id

    def close_position(
        self,
        position_id: int,
        exit_price: float,
        reason: str = "manual"
    ) -> Optional[Dict]:
        """
        Закрывает позицию и рассчитывает P&L.
        
        Args:
            position_id: ID позиции
            exit_price: Цена закрытия
            reason: Причина (sell/resolved)
        
        Returns:
            Данные закрытой позиции с P&L
        """
        position = self.database.get_position(position_id)
        if not position:
            logger.error(f"Позиция ID={position_id} не найдена в БД!")
            return None

        pnl = (exit_price - position.entry_price) * position.amount
        pnl_percent = ((exit_price - position.entry_price) / position.entry_price) * 100

        self.database.close_position(
            position_id=position_id,
            exit_price=exit_price,
            pnl=pnl
        )

        return {
            'position_id': position_id,
            'market_title': position.market_title,
            'outcome': position.outcome,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size': position.amount,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'reason': reason
        }

    def update_position_size(self, position_id: int, new_size: float):
        """
        Обновляет размер позиции (для частичного закрытия).
        
        Args:
            position_id: ID позиции
            new_size: Новый размер позиции
        """
        from src.database.models import Position
        
        session = self.database.get_session()
        try:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                old_size = position.amount
                position.amount = new_size
                session.commit()
                logger.debug(f"Обновлён размер позиции ID={position_id}: {old_size:.2f} → {new_size:.2f}")
            else:
                logger.error(f"Позиция ID={position_id} не найдена для обновления размера")
        except Exception as e:
            logger.error(f"Ошибка при обновлении размера позиции: {e}")
            session.rollback()
        finally:
            session.close()

    def get_open_positions(self) -> List:
        """Получает все открытые позиции."""
        return self.database.get_open_positions()

    def get_position_by_market(self, market_id: str, outcome: str) -> Optional:
        """Находит открытую позицию по рынку и исходу."""
        open_positions = self.get_open_positions()
        
        logger.debug(f"Поиск позиции: market={market_id[:8]}... outcome={outcome} среди {len(open_positions)} открытых")
        
        for pos in open_positions:
            logger.debug(f"  Сравниваю: {pos.market_id[:8]}... {pos.outcome} vs {market_id[:8]}... {outcome}")
            
            if pos.market_id == market_id and pos.outcome == outcome:
                logger.debug(f"  ✅ Найдено совпадение! PosID={pos.id}")
                return pos
        
        logger.debug(f"  ❌ Совпадений не найдено")
        return None

    def update_positions_with_current_prices(self):
        """Обновляет текущие цены для открытых позиций."""
        pass

    def get_statistics(self) -> Dict:
        """
        Получает статистику по всем позициям.
        """
        all_positions = self.database.get_all_positions()
        closed_positions = [p for p in all_positions if p.status == 'closed']
        open_positions = [p for p in all_positions if p.status == 'open']

        total_pnl = sum(p.pnl or 0 for p in closed_positions)
        winning_trades = len([p for p in closed_positions if (p.pnl or 0) > 0])
        losing_trades = len([p for p in closed_positions if (p.pnl or 0) < 0])
        win_rate = (winning_trades / len(closed_positions) * 100) if closed_positions else 0

        return {
            'total_positions': len(all_positions),
            'open_positions': len(open_positions),
            'closed_positions': len(closed_positions),
            'total_pnl': float(total_pnl),
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades
        }