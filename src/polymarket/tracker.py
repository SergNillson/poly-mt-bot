"""
Модуль для отслеживания сделок целевого трейдера.
Периодически проверяет новые сделки и уведомляет о них.
"""

import time
import logging
from datetime import datetime
from typing import Callable, List, Dict, Optional
from src.polymarket.api_client import PolymarketAPIClient
from src.database.database import Database

logger = logging.getLogger(__name__)


class TraderTracker:
    """
    Отслеживает сделки целевого трейдера на Polymarket.
    """
    
    def __init__(self, 
                 trader_address: str, 
                 api_client: PolymarketAPIClient,
                 database: Database,
                 check_interval: int = 30):
        """
        Инициализация трекера.
        
        Args:
            trader_address: Адрес кошелька отслеживаемого трейдера
            api_client: Клиент для работы с Polymarket API
            database: База данных для сохранения сделок
            check_interval: Интервал проверки в секундах (по умолчанию 30)
        """
        self.trader_address = trader_address
        self.api_client = api_client
        self.database = database
        self.check_interval = check_interval
        
        # Время последней проверки
        self.last_check_time = datetime.utcnow()
        
        # Callback функция для обработки новых сделок
        self.on_new_trade_callback: Optional[Callable] = None
        
        # Флаг для остановки мониторинга
        self.is_running = False
        
        logger.info(f"Инициализирован трекер для {trader_address[:8]}...")
    
    def set_new_trade_callback(self, callback: Callable):
        """
        Устанавливает функцию, которая будет вызываться при обнаружении новой сделки.
        
        Args:
            callback: Функция с сигнатурой callback(trade_data: Dict)
        """
        self.on_new_trade_callback = callback
        logger.info("Установлен callback для новых сделок")
    
    def start_monitoring(self):
        """
        Запускает мониторинг сделок трейдера.
        Работает в бесконечном цикле до вызова stop_monitoring().
        """
        self.is_running = True
        logger.info(f"Начат мониторинг трейдера {self.trader_address[:8]}...")
        logger.info(f"Интервал проверки: {self.check_interval} секунд")
        
        while self.is_running:
            try:
                # Получаем последние сделки
                trades = self.api_client.get_trader_trades(
                    self.trader_address, 
                    limit=50
                )
                
                # Проверяем каждую сделку
                new_trades = []
                for trade in trades:
                    if self.api_client.is_new_trade(trade, self.last_check_time):
                        new_trades.append(trade)
                
                # Обрабатываем новые сделки
                if new_trades:
                    logger.info(f"Обнаружено {len(new_trades)} новых сделок")
                    for trade in new_trades:
                        self._process_new_trade(trade)
                
                # Обновляем время последней проверки
                self.last_check_time = datetime.utcnow()
                
                # Ждём до следующей проверки
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки (Ctrl+C)")
                self.stop_monitoring()
                break                
            except Exception as e:
                logger.error(f"Ошибка при мониторинге: {e}", exc_info=True)
                # Продолжаем работу даже при ошибке
                time.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """
        Останавливает мониторинг.
        """
        logger.info("Остановка мониторинга...")
        self.is_running = False
    
    def _process_new_trade(self, trade: Dict):
        """
        Обрабатывает новую сделку трейдера.
        
        Args:
            trade: Данные сделки от API
        """
        try:
            # Парсим данные сделки
            parsed_trade = self.api_client.parse_trade_data(trade)
            
            # Получаем информацию о рынке
            market_info = self.api_client.get_market_info(parsed_trade['market_id'])
            market_title = market_info.get('question', 'Unknown Market') if market_info else 'Unknown Market'
            
            # Проверяем, не сохранена ли уже эта сделка
            existing = self.database.get_tracked_trade_by_hash(parsed_trade['transaction_hash'])
            if existing:
                logger.debug(f"Сделка {parsed_trade['transaction_hash'][:8]}... уже в БД")
                return
            
            # Сохраняем сделку в БД
            db_trade = self.database.add_tracked_trade(
                trader_address=self.trader_address,
                market_id=parsed_trade['market_id'],
                market_title=market_title,
                outcome=parsed_trade['outcome'],
                amount=parsed_trade['size'],
                price=parsed_trade['price'],
                tx_hash=parsed_trade['transaction_hash']
            )
            
            logger.info(f"💰 Новая сделка: {market_title}")
            logger.info(f"   Направление: {parsed_trade['outcome']} @ ${parsed_trade['price']:.3f}")
            logger.info(f"   Размер: ${parsed_trade['size']:.2f}")
            
            # Вызываем callback если установлен
            if self.on_new_trade_callback:
                self.on_new_trade_callback({
                    'db_trade': db_trade,
                    'parsed_trade': parsed_trade,
                    'market_title': market_title
                })
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сделки: {e}", exc_info=True)
    
    def get_trader_stats(self) -> Dict:
        """
        Возвращает статистику по отслеживаемому трейдеру.
        
        Returns:
            Словарь со статистикой
        """
        # Здесь можно добавить различную статистику
        # Например, количество сделок за период, средний размер и т.д.
        return {
            'trader_address': self.trader_address,
            'is_monitoring': self.is_running,
            'last_check': self.last_check_time,
            'check_interval': self.check_interval
        }