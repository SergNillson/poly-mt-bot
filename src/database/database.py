"""
Модуль для работы с базой данных.
"""

import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base, TrackedTrade, PaperTrade, Position, BalanceHistory


class Database:

    def __init__(self, db_path: str):
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self.Session()

    # === Відслідковувані угоди ===

    def add_tracked_trade(self, trader_address: str, market_id: str, market_title: str,
                          outcome: str, amount: float, price: float, tx_hash: str) -> TrackedTrade:
        session = self.get_session()
        try:
            trade = TrackedTrade(
                trader_address=trader_address,
                market_id=market_id,
                market_title=market_title,
                outcome=outcome,
                amount=amount,
                price=price,
                transaction_hash=tx_hash
            )
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
        finally:
            session.close()

    def get_tracked_trade_by_hash(self, tx_hash: str) -> TrackedTrade:
        session = self.get_session()
        try:
            return session.query(TrackedTrade).filter_by(transaction_hash=tx_hash).first()
        finally:
            session.close()

    # === Віртуальні угоди ===

    def add_paper_trade(self, tracked_trade_id: int, market_id: str, market_title: str,
                        outcome: str, amount: float, price: float) -> PaperTrade:
        session = self.get_session()
        try:
            trade = PaperTrade(
                tracked_trade_id=tracked_trade_id,
                market_id=market_id,
                market_title=market_title,
                outcome=outcome,
                amount=amount,
                price=price
            )
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
        finally:
            session.close()

    def close_paper_trade(self, trade_id: int, pnl: float):
        session = self.get_session()
        try:
            trade = session.query(PaperTrade).filter_by(id=trade_id).first()
            if trade:
                trade.status = 'closed'
                trade.pnl = pnl
                trade.closed_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def get_open_paper_trades(self):
        session = self.get_session()
        try:
            return session.query(PaperTrade).filter_by(status='open').all()
        finally:
            session.close()

    # === Позиції ===

    def add_position(self, market_id: str, market_title: str, outcome: str,
                     amount: float, entry_price: float, tracked_trade_id: int = None,
                     paper_trade_id: int = None) -> int:
        session = self.get_session()
        try:
            position = Position(
                market_id=market_id,
                market_title=market_title,
                outcome=outcome,
                amount=amount,
                entry_price=entry_price,
                current_price=entry_price,
                status='open'
            )
            session.add(position)
            session.commit()
            return position.id
        finally:
            session.close()

    def get_position(self, position_id: int):
        session = self.get_session()
        try:
            return session.query(Position).filter_by(id=position_id).first()
        finally:
            session.close()

    def get_open_positions(self):
        session = self.get_session()
        try:
            return session.query(Position).filter_by(status='open').all()
        finally:
            session.close()

    def get_closed_positions(self):
        session = self.get_session()
        try:
            return session.query(Position).filter_by(status='closed').all()
        finally:
            session.close()

    def get_all_positions(self):
        session = self.get_session()
        try:
            return session.query(Position).all()
        finally:
            session.close()

    def close_position(self, position_id: int, exit_price: float, pnl: float) -> bool:
        session = self.get_session()
        try:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                position.status = 'closed'
                position.exit_price = exit_price
                position.pnl = pnl
                position.closed_at = datetime.utcnow()
                session.commit()
                return True
            return False
        finally:
            session.close()

    def update_position(self, position_id: int, current_price: float, unrealized_pnl: float):
        session = self.get_session()
        try:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                position.current_price = current_price
                position.unrealized_pnl = unrealized_pnl
                session.commit()
        finally:
            session.close()

    def remove_position(self, position_id: int):
        session = self.get_session()
        try:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                session.delete(position)
                session.commit()
        finally:
            session.close()

    # === Баланс ===

    def add_balance_record(self, balance: float, change: float = 0.0, reason: str = None):
        session = self.get_session()
        try:
            record = BalanceHistory(
                balance=balance,
                change=change,
                reason=reason
            )
            session.add(record)
            session.commit()
            return record
        finally:
            session.close()

    def get_current_balance(self) -> float:
        session = self.get_session()
        try:
            last_record = session.query(BalanceHistory).order_by(
                BalanceHistory.timestamp.desc()
            ).first()
            return last_record.balance if last_record else None
        finally:
            session.close()