"""
Модуль для настройки логирования.
Создает красивые цветные логи в консоли и сохраняет их в файл.
"""

import logging
import colorlog
import os
from datetime import datetime


def setup_logger(name: str, log_file: str = None, level: str = "INFO", console: bool = True):
    """
    Создает и настраивает logger.
    
    Args:
        name: Имя logger'а
        log_file: Путь к файлу для сохранения логов
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        console: Выводить ли логи в консоль
    
    Returns:
        Настроенный logger
    """
    # Создаем logger
    logger = colorlog.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Удаляем существующие handlers, чтобы избежать дублирования
    logger.handlers = []
    
    # Формат для логов
    log_format = '%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Настройка цветов для разных уровней
    log_colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    
    # Handler для вывода в консоль (цветной)
    if console:
        console_handler = colorlog.StreamHandler()
        console_formatter = colorlog.ColoredFormatter(
            log_format,
            datefmt=date_format,
            log_colors=log_colors
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # Handler для записи в файл (без цветов)
    if log_file:
        # Создаем директорию для логов, если её нет
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_format = '[%(asctime)s] %(levelname)-8s %(message)s'
        file_formatter = logging.Formatter(file_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_banner(logger, mode: str = "PAPER"):
    """
    Выводит красивый баннер при запуске бота.
    
    Args:
        logger: Logger объект
        mode: Режим работы (PAPER или LIVE)
    """
    logger.info("═" * 50)
    logger.info("🤖 Polymarket Copy Trading Bot")
    logger.info(f"📄 Mode: {mode} TRADING")
    logger.info("═" * 50)
