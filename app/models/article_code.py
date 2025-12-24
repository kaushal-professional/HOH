"""
Article Code and Promoter models.
Database models for barcode scanning and promoter management.
"""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class ArticleCode(Base):
    """Article Code model - stores product article codes and promoter mapping"""
    __tablename__ = "article_codes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    products = Column(String(255), nullable=False, index=True)
    article_codes = Column(BigInteger, nullable=False, unique=True, index=True)
    promoter = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<ArticleCode(id={self.id}, article_code={self.article_codes}, product='{self.products}')>"


class Promoter(Base):
    """Promoter model - stores promoter information by state and point of sale"""
    __tablename__ = "promoter"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state = Column(String(100), nullable=False, index=True)
    point_of_sale = Column(String(255), nullable=False, index=True)
    promoter = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Promoter(id={self.id}, state='{self.state}', pos='{self.point_of_sale}')>"
