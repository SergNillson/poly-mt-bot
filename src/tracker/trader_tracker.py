"""
Async TraderTracker — обгортка над PolymarketAPIClient та Database.
Використовується в main.py для відслідковування нових угод трейдера.
"""

import logging
from datetime import datetime, timedelta
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
        self.trader_address = trader_address.lower()
        self.api_client = api_client
        self.database = database
        self.check_interval = check_interval
        self.processed_tx_hashes = set()  # Кэш обработанных транзакций
        
        # Стартуем с текущего времени минус 1 минута
        self.last_check_time = datetime.utcnow() - timedelta(minutes=1)

        logger.info(f"TraderTracker ініціалізовано для {trader_address[:8]}...")
        logger.info(f"🕐 Начальное время проверки: {self.last_check_time}")

    async def check_for_new_trades(self) -> Dict[str, List[Dict]]:
        """
        Перевіряє нові угоди трейдера з моменту останньої перевірки.

        Returns:
            Словарь: {'buys': [...], 'sells': [...]}
        """
        new_buys = []
        new_sells = []
        max_trade_time = self.last_check_time

        try:
            # Получаем активности (trades + positions + resolves)
            raw_activities = self.api_client.get_trader_trades(
                self.trader_address,
                limit=50
            )

            logger.info(f"   └─ Получено активностей от API: {len(raw_activities)}")

            if not raw_activities:
                return {'buys': [], 'sells': []}

            for idx, activity in enumerate(raw_activities):
                try:
                    parsed_activity = self.api_client.parse_trade_data(activity)
                    activity_time = parsed_activity['timestamp']
                    tx_hash = parsed_activity.get('transaction_hash')
                    activity_type = parsed_activity.get('type', 'TRADE')
                    
                    # ✅ ФИЛЬТР 1: обрабатываем только TRADE и POSITION_CLOSE
                    if activity_type not in ['TRADE', 'POSITION_CLOSE']:
                        logger.debug(f"   └─ Активность {idx+1}: пропущена (type={activity_type})")
                        continue
                    
                    # Обновляем максимальное время
                    if activity_time > max_trade_time:
                        max_trade_time = activity_time
                    
                    # ✅ ФИЛЬТР 2: Новая ли сделка по времени?
                    if activity_time <= self.last_check_time:
                        continue
                    
                    # ✅ ФИЛЬТР 3: Проверяем tx_hash
                    if not tx_hash:
                        logger.warning(f"   ⚠️ Сделка без tx_hash — пропускаю")
                        continue
                    
                    # ✅ ФИЛЬТР 4: Уже обработана в этой сессии?
                    if tx_hash in self.processed_tx_hashes:
                        logger.debug(f"   └─ Сделка {idx+1}: уже обработана в кэше (tx: {tx_hash[:10]}...)")
                        continue
                    
                    # ✅ ФИЛЬТР 5: Уже в БД?
                    if self.database.get_tracked_trade_by_hash(tx_hash):
                        logger.debug(f"   └─ Сделка {idx+1}: уже в БД (tx: {tx_hash[:10]}...)")
                        self.processed_tx_hashes.add(tx_hash)  # Добавляем в кэш
                        continue

                    logger.info(f"   ✅ Новая сделка! [{parsed_activity['side']}] {parsed_activity['title'][:30]}... tx={tx_hash[:10]}...")

                    # Получаем название рынка
                    market_title = parsed_activity.get('title', 'Unknown Market')

                    # Сохраняем в БД
                    db_trade = self.database.add_tracked_trade(
                        trader_address=self.trader_address,
                        market_id=parsed_activity['market_id'],
                        market_title=market_title,
                        outcome=parsed_activity['outcome'],
                        amount=parsed_activity['size'],
                        price=parsed_activity['price'],
                        tx_hash=tx_hash
                    )
                    
                    # ✅ ДОБАВЛЯЕМ В КЭШ
                    self.processed_tx_hashes.add(tx_hash)

                    trade_data = {
                        'db_trade': db_trade,
                        'parsed_trade': parsed_activity,
                        'market_title': market_title
                    }

                    # Разделяем на покупки и продажи
                    if parsed_activity['side'] == 'BUY':
                        new_buys.append(trade_data)
                        logger.info(f"      └─ Добавлена в BUY")
                    elif parsed_activity['side'] == 'SELL':
                        new_sells.append(trade_data)
                        logger.info(f"      └─ Добавлена в SELL")

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки активности {idx+1}: {e}", exc_info=True)

            # Обновляем last_check_time
            if max_trade_time > self.last_check_time:
                logger.info(f"🕐 Обновляю last_check_time: {self.last_check_time} → {max_trade_time}")
                self.last_check_time = max_trade_time
                
                # ✅ Очищаем кэш старых транзакций
                self._cleanup_cache()

        except Exception as e:
            logger.error(f"❌ Ошибка при получении активностей: {e}", exc_info=True)

        return {'buys': new_buys, 'sells': new_sells}
    
    def _cleanup_cache(self):
        """Очищает кэш обработанных транзакций (оставляет последние 100)."""
        if len(self.processed_tx_hashes) > 100:
            # Оставляем только последние 100 (FIFO)
            self.processed_tx_hashes = set(list(self.processed_tx_hashes)[-100:])
            logger.debug(f"Очищен кэш tx_hashes, осталось: {len(self.processed_tx_hashes)}")