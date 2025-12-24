"""
Stock Take models for managing stock take operations.
Database models for stock_take, open_stock, and close_stock tables.
"""

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class StockTake(Base):
    """Stock Take model - stores stock take information"""
    __tablename__ = "stock_take"

    stock_take_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    store_name = Column(String(255), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    status = Column(String(50), default='active', nullable=False, index=True)  # active, completed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    open_stocks = relationship("OpenStock", back_populates="stock_take", cascade="all, delete-orphan")
    close_stocks = relationship("CloseStock", back_populates="stock_take", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StockTake(stock_take_id='{self.stock_take_id}', store='{self.store_name}', status='{self.status}')>"


class OpenStock(Base):
    """Open Stock model - stores opening stock quantities"""
    __tablename__ = "open_stock"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stock_take_id = Column(UUID(as_uuid=True), ForeignKey('stock_take.stock_take_id', ondelete='CASCADE'), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    promoter_name = Column(String(255), nullable=False, index=True)
    open_qty = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    stock_take = relationship("StockTake", back_populates="open_stocks")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('stock_take_id', 'product_name', 'promoter_name', name='uq_open_stock_entry'),
    )

    def __repr__(self):
        return f"<OpenStock(id={self.id}, product='{self.product_name}', promoter='{self.promoter_name}', qty={self.open_qty})>"


class CloseStock(Base):
    """Close Stock model - stores closing stock quantities"""
    __tablename__ = "close_stock"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stock_take_id = Column(UUID(as_uuid=True), ForeignKey('stock_take.stock_take_id', ondelete='CASCADE'), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    promoter_name = Column(String(255), nullable=False, index=True)
    close_qty = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    stock_take = relationship("StockTake", back_populates="close_stocks")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('stock_take_id', 'product_name', 'promoter_name', name='uq_close_stock_entry'),
    )

    def __repr__(self):
        return f"<CloseStock(id={self.id}, product='{self.product_name}', promoter='{self.promoter_name}', qty={self.close_qty})>"
