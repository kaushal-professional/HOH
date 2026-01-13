"""
Price POS model for database operations.
Maps Point of Sale (stores) to pricelists with state and promoter information.
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class PricePos(Base):
    """
    Price POS model - maps point of sale to pricelist.

    Table: price_pos
    Stores the relationship between stores (point of sale) and their pricelists,
    along with state and promoter information.
    """
    __tablename__ = "price_pos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state = Column(String(100), nullable=False, index=True)
    point_of_sale = Column(String(255), nullable=False, index=True)
    promoter = Column(String(255), nullable=False, index=True)
    pricelist = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<PricePos(id={self.id}, pos='{self.point_of_sale}', pricelist='{self.pricelist}')>"
