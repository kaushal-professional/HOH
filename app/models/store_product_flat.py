"""
Store Product Flat Table Model.
Database model for the flat store_product table (singular).
This stores the raw Excel data: ykey, product_name, store, state
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class StoreProductFlat(Base):
    """Store Product Flat model - stores raw Excel data"""
    __tablename__ = "store_product"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ykey = Column(String, nullable=False, index=True)  # Product Y KEY (e.g., Y0520)
    product_name = Column(String, nullable=False)  # Product description/name
    store = Column(String, nullable=False, index=True)  # Store name
    state = Column(String, nullable=False, index=True)  # State name
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<StoreProductFlat(id={self.id}, ykey='{self.ykey}', store='{self.store}')>"
