"""
Async TraderTracker — обгортка над PolymarketAPIClient та Database.
Використовується в main.py для відслідковування нових угод трейдера.
"""

import logging
from datetime import datetime, timedelta, timezone
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
        
        # ✅ ИСПРАВЛЕНО: Используем UTC с timezone
        self.last_check_time = datetime.now(timezone.utc) - timedelta(minutes=1)

        logger.info(f"TraderTracker ініціалізовано для {trader_address[:10]}...")
        logger.info(f"🕐 Начальное время проверки: {self.last_check_time}")

    async def check_for_new_trades(self) -> Dict[str, List[Dict]]:
        """
        Перевіряє нові угоди трейдера з моменту останньої перевірки.

        Returns:
            Словарь: {'buys': [], 'sells': []}
        """
        new_buys = []
        new_sells = []
        max_trade_time = self.last_check_time

        try:
            # Получаем активности
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
                    
                    # ✅ DEBUG: Логируем первые 3 активности для проверки
                    if idx < 3:
                        logger.debug(
                            f"   └─ Активность {idx+1}: "
                            f"time={activity_time}, "
                            f"last_check={self.last_check_time}, "
                            f"type={activity_type}, "
                            f"side={parsed_activity.get('side')}"
                        )
                    
                    # ✅ ФИЛЬТР 1: обрабатываем TRADE, POSITION_CLOSE и REDEEM
                    if activity_type not in ['TRADE', 'POSITION_CLOSE', 'REDEEM']:
                        logger.debug(f"   └─ Активность {idx+1}: пропущена (type={activity_type})")
                        continue
                    
                    # Обновляем максимальное время
                    if activity_time > max_trade_time:
                        max_trade_time = activity_time
                    
                    # ✅ ФИЛЬТР 2: Новая ли сделка по времени?
                    if activity_time <= self.last_check_time:
                        logger.debug(f"   └─ Активность {idx+1}: старая ({activity_time} <= {self.last_check_time})")
                        continue
                    
                    # ✅ ФИЛЬТР 3: Проверяем tx_hash
                    if not tx_hash:
                        logger.debug(f"   └─ Активность {idx+1}: нет tx_hash, пропущена")
                        continue
                    
                    # ✅ ФИЛЬТР 4: Уже обработана?
                    if tx_hash in self.processed_tx_hashes:
                        logger.debug(f"   └─ Активность {idx+1}: уже обработана {tx_hash[:10]}...")
                        continue
                    
                    # ✅ ФИЛЬТР 5: side = BUY или SELL?
                    side = parsed_activity.get('side', '').upper()
                    
                    # ✅ ИСПРАВЛЕНО: Обрабатываем POSITION_CLOSE и REDEEM как SELL
                    if activity_type in ['POSITION_CLOSE', 'REDEEM']:
                        side = 'SELL'
                    
                    if side == 'BUY':
                        logger.info(f"   ✅ Новая сделка! [BUY] {parsed_activity['title'][:30]}... tx={tx_hash[:10]}...")
                        new_buys.append(parsed_activity)
                        self.processed_tx_hashes.add(tx_hash)
                        logger.info(f"      └─ Добавлена в BUY")
                    elif side == 'SELL':
                        logger.info(f"   ✅ Новая сделка! [SELL/{activity_type}] {parsed_activity['title'][:30]}... tx={tx_hash[:10]}...")
                        new_sells.append(parsed_activity)
                        self.processed_tx_hashes.add(tx_hash)
                        logger.info(f"      └─ Добавлена в SELL")
                    else:
                        logger.debug(f"   └─ Активность {idx+1}: неизвестный side={side}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при парсинге активности {idx+1}: {e}")
                    continue

            # Обновляем last_check_time
            if max_trade_time > self.last_check_time:
                logger.info(f"🕐 Обновляю last_check_time: {self.last_check_time} → {max_trade_time}")
                self.last_check_time = max_trade_time

            return {
                'buys': new_buys,
                'sells': new_sells
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при получении активностей: {e}")
            import traceback
            traceback.print_exc()
            return {'buys': [], 'sells': []}