"""
Pydantic schemas for Price Consolidated.
Request and response models for price_consolidated API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal


# ============================================================================
# Price Consolidated Schemas
# ============================================================================

class PriceConsolidatedBase(BaseModel):
    """Base schema for PriceConsolidated"""
    pricelist: str = Field(..., max_length=255, description="Pricelist or store name")
    product: str = Field(..., max_length=255, description="Product name")
    price: Decimal = Field(..., description="Product price (without GST)", ge=0)
    gst: Optional[Decimal] = Field(None, description="GST percentage (e.g., 0.05 for 5%, 0.18 for 18%)", ge=0, le=1)


class PriceConsolidatedCreate(PriceConsolidatedBase):
    """Schema for creating a new price consolidated entry"""
    pass


class PriceConsolidatedUpdate(BaseModel):
    """Schema for updating a price consolidated entry"""
    pricelist: Optional[str] = Field(None, max_length=255, description="Pricelist or store name")
    product: Optional[str] = Field(None, max_length=255, description="Product name")
    price: Optional[Decimal] = Field(None, description="Product price (without GST)", ge=0)
    gst: Optional[Decimal] = Field(None, description="GST percentage", ge=0, le=1)


class PriceConsolidatedResponse(PriceConsolidatedBase):
    """Schema for price consolidated response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PriceConsolidatedBulkCreate(BaseModel):
    """Schema for bulk creating price consolidated entries"""
    entries: List[PriceConsolidatedCreate] = Field(..., description="List of price consolidated entries to create")


# ============================================================================
# Query and Filter Schemas
# ============================================================================

class PriceConsolidatedFilter(BaseModel):
    """Schema for filtering price consolidated entries"""
    pricelist: Optional[str] = Field(None, description="Filter by pricelist (partial match)")
    product: Optional[str] = Field(None, description="Filter by product name (partial match)")
    min_price: Optional[Decimal] = Field(None, description="Minimum price filter", ge=0)
    max_price: Optional[Decimal] = Field(None, description="Maximum price filter", ge=0)
    has_gst: Optional[bool] = Field(None, description="Filter by GST presence (true=has GST, false=no GST)")
    search: Optional[str] = Field(None, description="Search across pricelist and product fields")


class PriceConsolidatedListResponse(BaseModel):
    """Schema for paginated list of price consolidated entries"""
    items: List[PriceConsolidatedResponse]
    total: int
    skip: int
    limit: int


class PriceWithGSTResponse(BaseModel):
    """Schema for price with calculated GST"""
    id: int
    pricelist: str
    product: str
    price: Decimal
    gst: Optional[Decimal]
    price_with_gst: Optional[Decimal]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Statistics Schemas
# ============================================================================

class PriceConsolidatedStats(BaseModel):
    """Schema for price consolidated statistics"""
    total_entries: int
    unique_pricelists: int
    unique_products: int
    avg_price: Optional[Decimal]
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    entries_with_gst: int


class PriceConsolidatedGroupByPricelist(BaseModel):
    """Schema for grouping by pricelist"""
    pricelist: str
    count: int
    avg_price: Optional[Decimal]


class PriceConsolidatedGroupByProduct(BaseModel):
    """Schema for grouping by product"""
    product: str
    count: int
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    avg_price: Optional[Decimal]


# ============================================================================
# Price Lookup Schemas
# ============================================================================

class PriceLookupRequest(BaseModel):
    """Schema for price lookup request"""
    product: str = Field(..., description="Product name (exact or partial match)")
    pricelist: Optional[str] = Field(None, description="Pricelist name (optional)")


class PriceLookupResponse(BaseModel):
    """Schema for price lookup response"""
    found: bool
    entries: List[PriceWithGSTResponse]
    message: str


# ============================================================================
# Success/Error Response Schemas
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[dict] = None


class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    success: bool
    created_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    errors: List[str] = []


class CSVUploadResponse(BaseModel):
    """Response schema for CSV upload endpoint"""
    success: bool
    total_rows: int
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    processing_time_seconds: float


class CSVUpdateResponse(BaseModel):
    """Response schema for CSV update endpoint"""
    success: bool
    total_rows: int
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    not_found_count: int = 0
    matched_by_pricelist_product: int = 0
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    processing_time_seconds: float
