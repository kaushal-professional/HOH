"""
Pydantic schemas for Login model.

These schemas are used for request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class LoginBase(BaseModel):
    """Base schema for Login with common fields."""
    name: str = Field(..., max_length=255, description="Admin name")
    email: EmailStr = Field(..., description="Admin email address (unique)")


class LoginCreate(LoginBase):
    """Schema for creating a new admin login."""
    password: str = Field(..., min_length=6, max_length=255, description="Plain text password (will be hashed)")


class LoginUpdate(BaseModel):
    """Schema for updating an existing admin login (all fields optional)."""
    name: Optional[str] = Field(None, max_length=255, description="Admin name")
    email: Optional[EmailStr] = Field(None, description="Admin email address")
    password: Optional[str] = Field(None, min_length=6, max_length=255, description="Plain text password (will be hashed)")


class LoginOut(BaseModel):
    """Schema for login response (excludes password)."""
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class LoginAuth(BaseModel):
    """Schema for admin login request."""
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., description="Plain text password")


class LoginAuthResponse(BaseModel):
    """Schema for admin login response."""
    access_token: str
    token_type: str = "bearer"
    admin: LoginOut
