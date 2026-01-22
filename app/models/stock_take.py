"""
Stock Take models for managing stock take operations.
Database models for stock_take, open_stock, and close_stock tables.
All models are date-based and independent.
"""

from sqlalchemy import Column, Integer, String, Date, DateTime, UniqueConstraint, Float
from sqlalchemy.sql import func
from app.core.database import Base


class StockTake(Base):
    """Stock Take model - stores stock take metadata (store + date based)"""
    __tablename__ = "stock_take"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_name = Column(String(255), nullable=False, index=True)
    stock_date = Column(Date, nullable=False, index=True)
    status = Column(String(50), default='active', nullable=False, index=True)  # active, completed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Unique constraint: one stock take per store + date
    __table_args__ = (
        UniqueConstraint('store_name', 'stock_date', name='uq_stock_take_store_date'),
    )

    def __repr__(self):
        return f"<StockTake(id={self.id}, store='{self.store_name}', date='{self.stock_date}', status='{self.status}')>"


class OpenStock(Base):
    """Open Stock model - stores opening stock quantities (date-based, independent)"""
    __tablename__ = "open_stock"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_name = Column(String(255), nullable=False, index=True)
    open_date = Column(Date, nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    promoter_name = Column(String(255), nullable=False, index=True)
    open_qty = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Unique constraint: one entry per store + date + product + promoter
    __table_args__ = (
        UniqueConstraint('store_name', 'open_date', 'product_name', 'promoter_name', name='uq_open_stock_entry'),
    )

    def __repr__(self):
        return f"<OpenStock(id={self.id}, store='{self.store_name}', date='{self.open_date}', product='{self.product_name}', qty={self.open_qty})>"


class CloseStock(Base):
    """Close Stock model - stores closing stock quantities (date-based, independent of stock_take)"""
    __tablename__ = "close_stock"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_name = Column(String(255), nullable=False, index=True)
    close_date = Column(Date, nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    promoter_name = Column(String(255), nullable=False, index=True)
    close_qty = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Unique constraint: one entry per store + date + product + promoter
    __table_args__ = (
        UniqueConstraint('store_name', 'close_date', 'product_name', 'promoter_name', name='uq_close_stock_entry'),
    )

    def __repr__(self):
        return f"<CloseStock(id={self.id}, store='{self.store_name}', date='{self.close_date}', product='{self.product_name}', qty={self.close_qty})>"
