"""
Login model for database operations.
"""

from sqlalchemy import Column, Integer, String
from app.core.database import Base


class Login(Base):
    """
    Login table model matching the database schema.

    Table: login
    Stores admin login information.
    """
    __tablename__ = "login"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<Login(id={self.id}, name='{self.name}', email='{self.email}')>"
