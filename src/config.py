"""
Конфигурация бота с поддержкой нескольких трейдеров.
"""

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class BotConfig:
    """Конфигурация бота."""
    
    def __init__(self):
        # Трейдеры
        self.trader_addresses = self._parse_trader_addresses()
        
        # Копирование
        self.copy_ratio = float(os.getenv('COPY_RATIO', '0.01'))
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE', '100.0'))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '20'))
        
        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    def _parse_trader_addresses(self) -> List[str]:
        """Парсит адреса трейдеров из .env."""
        # Пробуем новый формат (несколько адресов)
        multi_addresses = os.getenv('TRACKED_TRADER_ADDRESSES', '')
        if multi_addresses:
            addresses = [addr.strip().lower() for addr in multi_addresses.split(',')]
            return [addr for addr in addresses if addr]
        
        # Фоллбек на старый формат (один адрес)
        single_address = os.getenv('TRACKED_TRADER_ADDRESS', '')
        if single_address:
            return [single_address.strip().lower()]
        
        return []
    
    def print_summary(self):
        """Печатает сводку конфигурации."""
        print("=" * 60)
        print("КОНФИГУРАЦИЯ БОТА")
        print("=" * 60)
        print(f"📍 Трейдеров отслеживается: {len(self.trader_addresses)}")
        for idx, addr in enumerate(self.trader_addresses, 1):
            print(f"   {idx}. {addr}")
        print(f"📊 Копирование: {self.copy_ratio * 100}%")
        print(f"💰 Макс. позиция: ${self.max_position_size}")
        print(f"⏱️  Интервал: {self.check_interval} сек")
        print("=" * 60)


# Singleton
_config = None

def get_config() -> BotConfig:
    """Получает экземпляр конфигурации."""
    global _config
    if _config is None:
        _config = BotConfig()
    return _config