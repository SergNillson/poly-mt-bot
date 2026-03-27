"""
Модуль для работы с базой данных SQLite.
Управляет сохранением и получением данных о сделках и позициях.
"""

import logging
from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base, Trade, Position

logger = logging.getLogger(__name__)


class Database:
    """
    Класс для работы с базой данных.
    """
    
    def __init__(self, db_path: str = 'data/trading.db'):
        """
        Инициализация базы данных.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"База данных инициализирована: {db_path}")
    
    def get_session(self) -> Session:
        """Возвращает новую сессию БД."""
        return self.SessionLocal()
    
    def add_trade(self, 
                  trader_address: str,
                  market_id: str,
                  outcome: str,
                  side: str,
                  price: float,
                  amount: float,
                  transaction_hash: str = None) -> int:
        """
        Добавляет новую сделку в БД.
        
        Returns:
            ID добавленной сделки
        """
        session = self.get_session()
        try:
            trade = Trade(
                trader_address=trader_address,
                market_id=market_id,
                outcome=outcome,
                side=side,
                price=price,
                amount=amount,
                transaction_hash=transaction_hash
            )
            session.add(trade)
            session.commit()
            trade_id = trade.id
            logger.debug(f"Сделка добавлена: ID={trade_id}")
            return trade_id
        finally:
            session.close()
    
    def add_position(self,
                     market_id: str,
                     market_title: str,
                     outcome: str,
                     amount: float,
                     entry_price: float) -> int:
        """
        Добавляет новую позицию в БД.
        
        Returns:
            ID добавленной позиции
        """
        session = self.get_session()
        try:
            position = Position(
                market_id=market_id,
                market_title=market_title,
                outcome=outcome,
                amount=amount,
                entry_price=entry_price,
                is_open=True
            )
            session.add(position)
            session.commit()
            position_id = position.id
            logger.debug(f"Позиция добавлена: ID={position_id}")
            return position_id
        finally:
            session.close()
    
    def get_position(self, position_id: int) -> Optional[Position]:
        """Получает позицию по ID."""
        session = self.get_session()
        try:
            return session.query(Position).filter_by(id=position_id).first()
        finally:
            session.close()
    
    def get_open_position_by_market(self, market_id: str, outcome: str) -> Optional[Position]:
        """
        Находит открытую позицию по market_id и outcome.
        
        Args:
            market_id: ID рынка
            outcome: Исход (Up/Down/Yes/No)
        
        Returns:
            Position объект или None
        """
        session = self.get_session()
        try:
            position = session.query(Position).filter_by(
                market_id=market_id,
                outcome=outcome,
                is_open=True
            ).first()
            
            return position
        finally:
            session.close()
    
    def close_position(self, position_id: int, exit_price: float, pnl: float):
        """Закрывает позицию."""
        session = self.get_session()
        try:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                position.is_open = False
                position.exit_price = exit_price
                position.pnl = pnl
                session.commit()
                logger.debug(f"Позиция закрыта: ID={position_id}, P&L=${pnl:.2f}")
        finally:
            session.close()
    
    def get_open_positions(self) -> List[Position]:
        """Возвращает все открытые позиции."""
        session = self.get_session()
        try:
            return session.query(Position).filter_by(is_open=True).all()
        finally:
            session.close()
    
    def get_closed_positions(self) -> List[Position]:
        """Возвращает все закрытые позиции."""
        session = self.get_session()
        try:
            return session.query(Position).filter_by(is_open=False).all()
        finally:
            session.close()
    
    def get_all_trades(self) -> List[Trade]:
        """Возвращает все сделки."""
        session = self.get_session()
        try:
            return session.query(Trade).all()
        finally:
            session.close()