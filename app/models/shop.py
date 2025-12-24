"""
Shop model for database operations.
"""

from sqlalchemy import Column, Integer, String, TIMESTAMP, text
from app.core.database import Base


class Shop(Base):
    """
    Shop table model matching the database schema.

    Table: shops
    Stores information about shops/stores in the system.
    """
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company = Column(String(255), nullable=False, index=True)
    users = Column(String(255), nullable=True, index=True)
    pos_shop_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP")
    )

    def __repr__(self):
        return f"<Shop(id={self.id}, company='{self.company}', pos_shop_name='{self.pos_shop_name}', email='{self.email}')>"
