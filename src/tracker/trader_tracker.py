"""
Async TraderTracker — обгортка над PolymarketAPIClient та Database.
Використовується в main.py для відслідковування нових угод трейдера.
"""

import logging
from datetime import datetime
from typing import List, Dict

from src.polymarket.api_client import PolymarketAPIClient
from src.database.database import Database

logger = logging.getLogger(__name__)


class TraderTracker:
    """
    Async-сумісний трекер угод цільового трейдера на Polymarket.
    """

    def __init__(self,
                 trader_address: str,
                 api_client: PolymarketAPIClient,
                 database: Database,
                 check_interval: int = 60):
        self.trader_address = trader_address
        self.api_client = api_client
        self.database = database
        self.check_interval = check_interval

        # Час останньої перевірки
        self.last_check_time = datetime.utcnow()

        logger.info(f"TraderTracker ініціалізовано для {trader_address[:8]}...")

    async def check_for_new_trades(self) -> List[Dict]:
        """
        Перевіряє нові угоди трейдера з моменту останньої перевірки.

        Returns:
            Список нових угод у форматі {'db_trade': ..., 'parsed_trade': ..., 'market_title': ...}
        """
        new_trades_result = []

        try:
            # Отримуємо останні угоди з API
            raw_trades = self.api_client.get_trader_trades(
                self.trader_address,
                limit=50
            )

            for trade in raw_trades:
                # Перевіряємо чи угода нова
                if not self.api_client.is_new_trade(trade, self.last_check_time):
                    continue

                try:
                    parsed_trade = self.api_client.parse_trade_data(trade)

                    # Пропускаємо якщо вже є в БД
                    tx_hash = parsed_trade.get('transaction_hash')
                    if tx_hash and self.database.get_tracked_trade_by_hash(tx_hash):
                        logger.debug(f"Угода {str(tx_hash)[:8]}... вже в БД, пропускаємо")
                        continue

                    # Отримуємо інфо про ринок
                    market_info = self.api_client.get_market_info(parsed_trade['market_id'])
                    market_title = (
                        market_info.get('question', 'Unknown Market')
                        if market_info else 'Unknown Market'
                    )

                    # Зберігаємо в БД
                    db_trade = self.database.add_tracked_trade(
                        trader_address=self.trader_address,
                        market_id=parsed_trade['market_id'],
                        market_title=market_title,
                        outcome=parsed_trade['outcome'],
                        amount=parsed_trade['size'],
                        price=parsed_trade['price'],
                        tx_hash=tx_hash
                    )

                    logger.info(
                        f"💰 Нова угода: {market_title} | "
                        f"{parsed_trade['outcome']} @ ${parsed_trade['price']:.3f} | "
                        f"Розмір: ${parsed_trade['size']:.2f}"
                    )

                    new_trades_result.append({
                        'db_trade': db_trade,
                        'parsed_trade': parsed_trade,
                        'market_title': market_title
                    })

                except Exception as e:
                    logger.error(f"Помилка обробки угоди: {e}", exc_info=True)

            # Оновлюємо час останньої перевірки
            self.last_check_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Помилка при отриманні угод: {e}", exc_info=True)

        return new_trades_result