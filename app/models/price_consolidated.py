"""
Price Consolidated model.
Database model for storing product prices by pricelist/store.
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class PriceConsolidated(Base):
    """Price Consolidated model - stores product prices by pricelist"""
    __tablename__ = "price_consolidated"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pricelist = Column(String(255), nullable=False, index=True)  # Store name or pricelist name
    product = Column(String(255), nullable=False, index=True)  # Product name
    price = Column(Numeric(10, 2), nullable=False)  # Price with 2 decimal places
    gst = Column(Numeric(5, 2), nullable=True)  # GST percentage (e.g., 0.05 for 5%, 0.18 for 18%)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<PriceConsolidated(id={self.id}, pricelist='{self.pricelist}', product='{self.product}', price={self.price}, gst={self.gst})>"
