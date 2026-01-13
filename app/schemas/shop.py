"""
Pydantic schemas for Shop model.

These schemas are used for request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class ShopBase(BaseModel):
    """Base schema for Shop with common fields."""
    company: str = Field(..., max_length=255, description="Company name")
    users: Optional[str] = Field(None, max_length=255, description="Associated users")
    pos_shop_name: str = Field(..., max_length=255, description="POS shop name")
    email: EmailStr = Field(..., description="Shop email address (unique)")


class ShopCreate(ShopBase):
    """Schema for creating a new shop."""
    password: str = Field(..., min_length=6, max_length=255, description="Plain text password (will be hashed)")


class ShopUpdate(BaseModel):
    """Schema for updating an existing shop (all fields optional)."""
    company: Optional[str] = Field(None, max_length=255, description="Company name")
    users: Optional[str] = Field(None, max_length=255, description="Associated users")
    pos_shop_name: Optional[str] = Field(None, max_length=255, description="POS shop name")
    email: Optional[EmailStr] = Field(None, description="Shop email address")
    password: Optional[str] = Field(None, min_length=6, max_length=255, description="Plain text password (will be hashed)")


class ShopOut(ShopBase):
    """Schema for shop response (excludes password)."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShopLogin(BaseModel):
    """Schema for shop login request."""
    email: EmailStr = Field(..., description="Shop email address")
    password: str = Field(..., description="Plain text password")


class ShopLoginResponse(BaseModel):
    """Schema for shop login response."""
    access_token: str
    token_type: str = "bearer"
    shop: ShopOut
