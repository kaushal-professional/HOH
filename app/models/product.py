"""
Product, State, Store, and Store-Product mapping models.
Database models for the store-product availability system.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Product(Base):
    """Product model - stores product information"""
    __tablename__ = "products"

    product_id = Column(String(20), primary_key=True, index=True)  # Y KEY (e.g., Y0520)
    product_type = Column(String(100), nullable=False, index=True)  # Almond, Cashew, etc.
    product_description = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    store_products = relationship("StoreProduct", back_populates="product", cascade="all, delete-orphan")
    state_products = relationship("StateProduct", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product(product_id='{self.product_id}', type='{self.product_type}')>"


class State(Base):
    """State/Region model"""
    __tablename__ = "states"

    state_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state_name = Column(String(100), nullable=False, unique=True, index=True)  # Delhi, Karnataka, etc.
    state_code = Column(String(10), nullable=True, unique=True)  # DL, KA, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    stores = relationship("Store", back_populates="state", cascade="all, delete-orphan")
    state_products = relationship("StateProduct", back_populates="state", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<State(state_id={self.state_id}, name='{self.state_name}')>"


class Store(Base):
    """Store model - represents physical stores"""
    __tablename__ = "stores"

    store_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_name = Column(String(255), nullable=False, index=True)
    store_code = Column(String(20), nullable=True, unique=True)
    email = Column(String(255), nullable=True, index=True)  # Links to user table
    state_id = Column(Integer, ForeignKey("states.state_id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    state = relationship("State", back_populates="stores")
    store_products = relationship("StoreProduct", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store(store_id={self.store_id}, name='{self.store_name}')>"


class StoreProduct(Base):
    """Junction table - Maps products to stores"""
    __tablename__ = "store_products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.store_id"), nullable=False, index=True)
    product_id = Column(String(20), ForeignKey("products.product_id"), nullable=False, index=True)
    is_available = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    store = relationship("Store", back_populates="store_products")
    product = relationship("Product", back_populates="store_products")

    # Unique constraint to prevent duplicate mappings
    __table_args__ = (
        UniqueConstraint('store_id', 'product_id', name='uq_store_product'),
    )

    def __repr__(self):
        return f"<StoreProduct(store_id={self.store_id}, product_id='{self.product_id}')>"


class StateProduct(Base):
    """Junction table - Maps products to states (optional state-level mapping)"""
    __tablename__ = "state_products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state_id = Column(Integer, ForeignKey("states.state_id"), nullable=False, index=True)
    product_id = Column(String(20), ForeignKey("products.product_id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    state = relationship("State", back_populates="state_products")
    product = relationship("Product", back_populates="state_products")

    # Unique constraint to prevent duplicate mappings
    __table_args__ = (
        UniqueConstraint('state_id', 'product_id', name='uq_state_product'),
    )

    def __repr__(self):
        return f"<StateProduct(state_id={self.state_id}, product_id='{self.product_id}')>"
