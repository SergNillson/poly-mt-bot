"""
Главный файл запуска бота для копирования сделок на Polymarket.
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Фикс кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from src.polymarket.api_client import PolymarketAPIClient
from src.tracker.trader_tracker import TraderTracker
from src.database.database import Database
from src.trading.position_manager import PositionManager
from src.trading.paper_trader import PaperTrader
from src.bot.telegram_bot import TelegramBot

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 60)
    logger.info("ЗАПУСК POLYMARKET COPY TRADING BOT")
    logger.info("=" * 60)

    required_vars = ['TRACKED_TRADER_ADDRESS', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        logger.error("Создайте файл .env на основе .env.example")
        sys.exit(1)

    tracked_trader_address = os.getenv('TRACKED_TRADER_ADDRESS')
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

    copy_ratio = float(os.getenv('COPY_RATIO', '1.0'))
    max_position_size = float(os.getenv('MAX_POSITION_SIZE', '100.0'))
    check_interval = int(os.getenv('CHECK_INTERVAL', '60'))

    logger.info(f"Трейдер: {tracked_trader_address}")
    logger.info(f"Копирование: {copy_ratio * 100}%")
    logger.info(f"Макс. позиция: ${max_position_size}")
    logger.info(f"Интервал: {check_interval} сек")
    logger.info("Инициализация компонентов...")

    os.makedirs('data', exist_ok=True)
    database = Database('data/trading.db')
    logger.info("База данных инициализирована")

    api_client = PolymarketAPIClient()
    logger.info("API клиент Polymarket инициализирован")

    position_manager = PositionManager(database, api_client)
    logger.info("Position Manager инициализирован")

    paper_trader = PaperTrader(
        position_manager=position_manager,
        database=database,
        api_client=api_client,
        copy_ratio=copy_ratio,
        max_position_size=max_position_size
    )
    logger.info("Paper Trader инициализирован")

    telegram_bot = TelegramBot(
        token=telegram_token,
        chat_id=telegram_chat_id,
        paper_trader=paper_trader
    )
    logger.info("Telegram Bot инициализирован")

    tracker = TraderTracker(
        trader_address=tracked_trader_address,
        api_client=api_client,
        database=database,
        check_interval=check_interval
    )
    logger.info("Trader Tracker инициализирован")

    await telegram_bot.send_message(
        "Bot started!\n\n"
        f"Trader: <code>{tracked_trader_address}</code>\n\n"
        f"Copy ratio: {copy_ratio * 100}%\n"
        f"Max position: ${max_position_size}\n"
        f"Interval: {check_interval} sec"
    )

    bot_task = asyncio.create_task(telegram_bot.start_polling())

    logger.info("Начинаем мониторинг сделок...")

    try:
        while True:
            try:
                new_trades = await tracker.check_for_new_trades()

                if new_trades:
                    logger.info(f"Новых сделок: {len(new_trades)}")

                    for trade_data in new_trades:
                        await telegram_bot.notify_new_trade(trade_data)

                        if paper_trader.should_copy_trade(trade_data):
                            position_id = paper_trader.copy_trade(trade_data)

                            if position_id:
                                parsed = trade_data['parsed_trade']
                                copy_amount = min(
                                    parsed['size'] * copy_ratio,
                                    max_position_size
                                )
                                await telegram_bot.notify_position_opened(
                                    position_id, trade_data, copy_amount
                                )
                        else:
                            logger.info("Сделка не соответствует критериям копирования")

                position_manager.update_positions_with_current_prices()
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}", exc_info=True)
                await asyncio.sleep(check_interval)

    except KeyboardInterrupt:
        logger.info("Остановка...")
        await telegram_bot.send_message("Bot stopped")
        paper_trader.print_statistics()
        await telegram_bot.stop_polling()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())