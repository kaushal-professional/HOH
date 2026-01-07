"""
Pydantic schemas for Article Code and Promoter.
Request and response models for API endpoints.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================================
# Article Code Schemas
# ============================================================================

class ArticleCodeBase(BaseModel):
    """Base schema for Article Code"""
    products: str = Field(..., max_length=255, description="Product name")
    article_codes: int = Field(..., description="Article barcode number")
    promoter: str = Field(..., max_length=255, description="Promoter name")


class ArticleCodeCreate(ArticleCodeBase):
    """Schema for creating a new article code"""
    pass


class ArticleCodeUpdate(BaseModel):
    """Schema for updating an article code"""
    products: Optional[str] = Field(None, max_length=255)
    article_codes: Optional[int] = None
    promoter: Optional[str] = Field(None, max_length=255)


class ArticleCodeResponse(ArticleCodeBase):
    """Schema for article code response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Barcode Scan Schemas
# ============================================================================

class BarcodeScanRequest(BaseModel):
    """Schema for barcode scan request (deprecated - use multipart form data instead)"""
    barcode: str = Field(..., description="Scanned barcode string")
    store_name: str = Field(..., max_length=255, description="Store name")


class BarcodeImageResult(BaseModel):
    """Schema for individual barcode detection result from image"""
    text: str = Field(..., description="Decoded barcode text")
    format: str = Field(..., description="Barcode format type")


class ArticleLookupRequest(BaseModel):
    """Schema for article lookup by name request"""
    article_name: str = Field(..., max_length=255, description="Product/Article name")
    store_name: str = Field(..., max_length=255, description="Store name")


class BarcodeScanResponse(BaseModel):
    """Schema for barcode scan response"""
    product: str = Field(..., description="Product name")
    article_code: int = Field(..., description="Article code extracted from barcode")
    store_name: str = Field(..., description="Store name")
    store_type: str = Field(..., description="Store type/format identified from barcode")
    promoter: str = Field(..., description="Promoter name")
    pricelist: str = Field(..., description="Pricelist name")
    price: Optional[float] = Field(None, description="Product price from pricelist (without GST)")
    gst: Optional[float] = Field(None, description="GST percentage (e.g., 0.05 for 5%, 0.18 for 18%)")
    price_with_gst: Optional[float] = Field(None, description="Product price including GST")
    weight: Optional[float] = Field(None, description="Weight in kilograms extracted from barcode")
    weight_code: str = Field(..., description="Weight code/format from barcode")
    barcode_format: str = Field(..., description="Barcode format type")

    class Config:
        from_attributes = True


# ============================================================================
# Promoter Schemas
# ============================================================================

class PromoterBase(BaseModel):
    """Base schema for Promoter"""
    state: str = Field(..., max_length=100, description="State name")
    point_of_sale: str = Field(..., max_length=255, description="Point of sale name")
    promoter: str = Field(..., max_length=255, description="Promoter name")


class PromoterCreate(PromoterBase):
    """Schema for creating a new promoter"""
    pass


class PromoterUpdate(BaseModel):
    """Schema for updating a promoter"""
    state: Optional[str] = Field(None, max_length=100)
    point_of_sale: Optional[str] = Field(None, max_length=255)
    promoter: Optional[str] = Field(None, max_length=255)


class PromoterResponse(PromoterBase):
    """Schema for promoter response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
