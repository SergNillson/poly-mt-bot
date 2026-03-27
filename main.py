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


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    # Отключаем лишние логи
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    logging.getLogger("src.polymarket.api_client").setLevel(logging.WARNING)
    logging.getLogger("src.bot.telegram_bot").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
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

    logger.info(f"📍 Трейдер: {tracked_trader_address}")
    logger.info(f"📊 Копирование: {copy_ratio * 100}%")
    logger.info(f"💰 Макс. позиция: ${max_position_size}")
    logger.info(f"⏱️  Интервал проверки: {check_interval} сек")
    logger.info("=" * 60)

    os.makedirs('data', exist_ok=True)
    database = Database('data/trading.db')

    api_client = PolymarketAPIClient()
    position_manager = PositionManager(database, api_client)

    paper_trader = PaperTrader(
        position_manager=position_manager,
        database=database,
        api_client=api_client,
        trader_address=tracked_trader_address,  # ⬅️ ДОБАВЛЕНО
        copy_ratio=copy_ratio,
        max_position_size=max_position_size
    )

    telegram_bot = TelegramBot(
        token=telegram_token,
        chat_id=telegram_chat_id,
        paper_trader=paper_trader
    )

    tracker = TraderTracker(
        trader_address=tracked_trader_address,
        api_client=api_client,
        database=database,
        check_interval=check_interval
    )

    # Показываем последние 3 сделки трейдера при старте
    logger.info("🔍 Проверяю последние сделки трейдера...")
    recent_trades = api_client.get_trader_trades(tracked_trader_address, limit=3)
    
    if recent_trades:
        logger.info(f"📋 Найдено последних сделок: {len(recent_trades)}")
        for trade in recent_trades[:3]:
            parsed = api_client.parse_trade_data(trade)
            logger.info(
                f"  └─ [{parsed['side']}] {parsed['title'][:35]}... "
                f"{parsed['outcome']} @ ${parsed['price']:.2f} | "
                f"${parsed['size']:.2f} | {parsed['timestamp'].strftime('%Y-%m-%d %H:%M')}"
            )
    else:
        logger.warning("⚠️  Сделки не найдены (возможно, неверный адрес трейдера)")
    
    logger.info("=" * 60)

    # Показываем текущую статистику
    stats = paper_trader.get_statistics()
    logger.info(f"💼 Текущая статистика:")
    logger.info(f"  └─ Открытых позиций: {stats['open_positions']}")
    logger.info(f"  └─ Закрытых позиций: {stats['closed_positions']}")
    logger.info(f"  └─ Общий P&L: ${stats['total_pnl']:.2f}")
    logger.info("=" * 60)

    # Запускаем Telegram бота
    bot_task = asyncio.create_task(telegram_bot.start_polling())

    logger.info("🚀 Начинаем мониторинг сделок...")
    logger.info("=" * 60)

    check_count = 0

    try:
        while True:
            try:
                check_count += 1
                logger.info(f"🔄 Проверка #{check_count} — {asyncio.get_event_loop().time():.0f}s")
                
                new_trades = await tracker.check_for_new_trades()

                if new_trades['buys'] or new_trades['sells']:
                    logger.info(f"🆕 Новых покупок: {len(new_trades['buys'])}, продаж: {len(new_trades['sells'])}")
                else:
                    logger.info("   └─ Новых сделок нет")

                # Обрабатываем покупки
                for trade_data in new_trades['buys']:
                    if paper_trader.should_copy_trade(trade_data):
                        paper_trader.copy_buy(trade_data)

                # Обрабатываем продажи
                for trade_data in new_trades['sells']:
                    paper_trader.copy_sell(trade_data)

                # Показываем статус открытых позиций каждые 5 проверок
                if check_count % 5 == 0:
                    stats = paper_trader.get_statistics()
                    logger.info(f"📊 Статус: {stats['open_positions']} открытых | P&L: ${stats['total_pnl']:.2f}")

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}", exc_info=True)
                await asyncio.sleep(check_interval)

    except KeyboardInterrupt:
        logger.info("⏸️  Остановка...")
        await telegram_bot.stop_polling()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())