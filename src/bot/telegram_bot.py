"""
Telegram бот для уведомлений и управления.
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram бот для отправки уведомлений и статистики.
    """

    def __init__(self, token: str, chat_id: str, paper_trader):
        self.token = token
        self.chat_id = chat_id
        self.paper_trader = paper_trader
        self.application = None
        self.scheduler = AsyncIOScheduler()

    async def start_polling(self):
        """Запускает Telegram бота."""
        self.application = Application.builder().token(self.token).build()

        # Команды
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("stats", self._stats_command))

        # Запускаем планировщик для автоматической отправки статистики
        self.scheduler.add_job(
            self.send_statistics,
            'interval',
            hours=1,
            id='send_statistics'
        )
        self.scheduler.start()

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop_polling(self):
        """Останавливает бота."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        self.scheduler.shutdown()

    async def send_statistics(self):
        """Отправляет статистику в Telegram."""
        stats = self.paper_trader.get_statistics()
        
        # Считаем использованный капитал
        positions = self.paper_trader.position_manager.get_open_positions()
        used_capital = sum(p.amount * p.entry_price for p in positions)
        
        # Виртуальный баланс
        total_capital = 1000.0  # Можно вынести в .env
        free_capital = total_capital - used_capital
        
        message = (
            f"📊 <b>Статистика</b>\n\n"
            f"💼 Открытых позиций: {stats['open_positions']}\n"
            f"✅ Закрытых позиций: {stats['closed_positions']}\n\n"
            f"💰 <b>Общий P&L: ${stats['total_pnl']:.2f}</b>\n\n"
            f"📈 Прибыльных: {stats['winning_trades']}\n"
            f"📉 Убыточных: {stats['losing_trades']}\n"
            f"🎯 Винрейт: {stats['win_rate']:.1f}%\n\n"
            f"💵 Используется: ${used_capital:.2f}\n"
            f"💸 Свободно: ${free_capital:.2f}\n"
            f"📊 Всего капитала: ${total_capital:.2f}"
        )

        await self.application.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode='HTML'
        )

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start."""
        await update.message.reply_text(
            "👋 Polymarket Copy Trading Bot запущен!\n\n"
            "Команды:\n"
            "/stats - показать статистику"
        )

    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats."""
        await self.send_statistics()