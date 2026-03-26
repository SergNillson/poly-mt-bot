"""
Модели базы данных для хранения информации о сделках и позициях.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class TrackedTrade(Base):
    __tablename__ = 'tracked_trades'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    trader_address = Column(String, nullable=False)
    market_id = Column(String, nullable=False)
    market_title = Column(String)
    outcome = Column(String)
    amount = Column(Float, nullable=False)
    price = Column(Float)
    transaction_hash = Column(String, unique=True)

    def __repr__(self):
        return f"<TrackedTrade {self.market_title} - ${self.amount}>"


class PaperTrade(Base):
    __tablename__ = 'paper_trades'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tracked_trade_id = Column(Integer)
    market_id = Column(String, nullable=False)
    market_title = Column(String)
    outcome = Column(String)
    amount = Column(Float, nullable=False)
    price = Column(Float)
    status = Column(String, default='open')
    pnl = Column(Float, default=0.0)
    closed_at = Column(DateTime)

    def __repr__(self):
        return f"<PaperTrade {self.market_title} - ${self.amount} ({self.status})>"


class Position(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True)
    paper_trade_id = Column(Integer)
    market_id = Column(String, nullable=False)
    market_title = Column(String)
    outcome = Column(String)
    amount = Column(Float, nullable=False)
    entry_price = Column(Float)
    current_price = Column(Float)
    exit_price = Column(Float)
    unrealized_pnl = Column(Float, default=0.0)
    pnl = Column(Float, default=0.0)
    status = Column(String, default='open')
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Position {self.market_title} - ${self.amount} ({self.status})>"


class BalanceHistory(Base):
    __tablename__ = 'balance_history'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    balance = Column(Float, nullable=False)
    change = Column(Float, default=0.0)
    reason = Column(String)

    def __repr__(self):
        return f"<Balance ${self.balance} at {self.timestamp}>"