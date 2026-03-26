"""
Telegram бот для мониторинга и управления копированием сделок.
"""

import logging
from typing import Optional
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from src.trading.paper_trader import PaperTrader

logger = logging.getLogger(__name__)


class TelegramBot:

    def __init__(self, token: str, chat_id: str, paper_trader: Optional[PaperTrader] = None):
        self.token = token
        self.chat_id = chat_id
        self.paper_trader = paper_trader
        self.bot = Bot(token=token)
        self.application = None
        logger.info("Telegram бот инициализирован")

    async def send_message(self, text: str, parse_mode: str = "HTML"):
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")

    async def notify_new_trade(self, trade_data: dict):
        parsed = trade_data['parsed_trade']
        market_title = trade_data['market_title']
        tx_hash = parsed.get('transaction_hash', 'N/A') or 'N/A'

        message = (
            f"🆕 <b>Новая сделка обнаружена</b>\n\n"
            f"📊 Рынок: {market_title}\n"
            f"📈 Outcome: <b>{parsed['outcome']}</b>\n"
            f"💰 Размер: ${parsed['size']:.2f}\n"
            f"💵 Цена: ${parsed['price']:.3f}\n"
            f"🔗 TX: <code>{str(tx_hash)[:16]}...</code>"
        )
        await self.send_message(message)

    async def notify_position_opened(self, position_id: int, trade_data: dict, copy_amount: float):
        parsed = trade_data['parsed_trade']
        market_title = trade_data['market_title']

        message = (
            f"✅ <b>Позиция открыта #{position_id}</b>\n\n"
            f"📊 Рынок: {market_title}\n"
            f"📈 Outcome: <b>{parsed['outcome']}</b>\n"
            f"💰 Размер: ${copy_amount:.2f}\n"
            f"💵 Цена входа: ${parsed['price']:.3f}"
        )
        await self.send_message(message)

    async def notify_position_closed(self, position_data: dict):
        pos = position_data
        pnl_emoji = "📈" if pos['pnl'] >= 0 else "📉"
        pnl_sign = "+" if pos['pnl'] >= 0 else ""

        message = (
            f"{pnl_emoji} <b>Позиция закрыта #{pos['id']}</b>\n\n"
            f"📊 Рынок: {pos['market_title']}\n"
            f"📈 Outcome: <b>{pos['outcome']}</b>\n"
            f"💵 Вход: ${pos['entry_price']:.3f}\n"
            f"💵 Выход: ${pos['exit_price']:.3f}\n"
            f"💰 P&L: <b>{pnl_sign}${pos['pnl']:.2f}</b>"
        )
        await self.send_message(message)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 <b>Polymarket Copy Trading Bot</b>\n\n"
            "Доступные команды:\n"
            "/stats - Статистика торговли\n"
            "/positions - Открытые позиции\n"
            "/help - Помощь",
            parse_mode="HTML"
        )

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.paper_trader:
            await update.message.reply_text("PaperTrader не инициализирован")
            return

        stats = self.paper_trader.get_statistics()
        message = (
            f"📊 <b>СТАТИСТИКА ТОРГОВЛИ</b>\n\n"
            f"💰 Реализованный P&L: <b>${stats['realized_pnl']:+.2f}</b>\n"
            f"💵 Нереализованный P&L: <b>${stats['unrealized_pnl']:+.2f}</b>\n"
            f"📈 Общий P&L: <b>${stats['total_pnl']:+.2f}</b>\n\n"
            f"📂 Открытых позиций: {stats['open_positions']}\n"
            f"📁 Закрытых позиций: {stats['closed_positions']}\n"
            f"🎯 Win Rate: {stats['win_rate']:.1f}%\n\n"
            f"⚙️ Коэффициент копирования: {stats['copy_ratio'] * 100}%\n"
            f"💼 Макс. размер позиции: ${stats['max_position_size']:.2f}"
        )
        await update.message.reply_text(message, parse_mode="HTML")

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.paper_trader:
            await update.message.reply_text("PaperTrader не инициализирован")
            return

        open_positions = self.paper_trader.position_manager.get_open_positions()

        if not open_positions:
            await update.message.reply_text("Нет открытых позиций")
            return

        message = f"📂 <b>ОТКРЫТЫЕ ПОЗИЦИИ ({len(open_positions)})</b>\n\n"

        for pos in open_positions:
            current_price = self.paper_trader.position_manager.get_position_current_price(pos)
            if current_price:
                unrealized_pnl = self.paper_trader.position_manager.calculate_pnl(
                    pos.amount, pos.entry_price, current_price
                )
                pnl_emoji = "📈" if unrealized_pnl >= 0 else "📉"
                message += (
                    f"{pnl_emoji} #{pos.id} {pos.outcome}\n"
                    f"   {pos.market_title[:40]}...\n"
                    f"   ${pos.entry_price:.3f} → ${current_price:.3f}\n"
                    f"   P&L: <b>${unrealized_pnl:+.2f}</b>\n\n"
                )
            else:
                message += (
                    f"📊 #{pos.id} {pos.outcome}\n"
                    f"   {pos.market_title[:40]}...\n"
                    f"   Вход: ${pos.entry_price:.3f}\n\n"
                )
        await update.message.reply_text(message, parse_mode="HTML")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "ℹ️ <b>Помощь</b>\n\n"
            "Этот бот копирует сделки выбранного трейдера на Polymarket.\n\n"
            "<b>Команды:</b>\n"
            "/start - Начало работы\n"
            "/stats - Показать статистику торговли\n"
            "/positions - Показать открытые позиции\n"
            "/help - Показать эту справку",
            parse_mode="HTML"
        )

    def setup_handlers(self):
        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("positions", self.cmd_positions))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        logger.info("Обработчики команд настроены")

    async def start_polling(self):
        if not self.application:
            self.setup_handlers()
        logger.info("Запуск Telegram бота (polling)...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop_polling(self):
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()