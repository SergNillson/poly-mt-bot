"""
Модели базы данных для SQLAlchemy.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Trade(Base):
    """
    Модель для хранения сделок трейдера.
    """
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trader_address = Column(String, nullable=False, index=True)
    market_id = Column(String, nullable=False, index=True)
    outcome = Column(String, nullable=False)  # Yes/No/Up/Down
    side = Column(String, nullable=False)  # BUY/SELL
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_hash = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Trade(id={self.id}, side={self.side}, market={self.market_id[:8]}...)>"


class Position(Base):
    """
    Модель для хранения позиций бота.
    """
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, nullable=False, index=True)
    market_title = Column(String, nullable=False)
    outcome = Column(String, nullable=False)  # Yes/No/Up/Down
    amount = Column(Float, nullable=False)  # Количество контрактов
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)  # Profit & Loss
    is_open = Column(Boolean, default=True, index=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    trader_tx_hash = Column(String, nullable=True)  # Хэш транзакции трейдера
    
    def __repr__(self):
        status = "OPEN" if self.is_open else "CLOSED"
        return f"<Position(id={self.id}, {status}, market={self.market_id[:8]}..., pnl={self.pnl})>"