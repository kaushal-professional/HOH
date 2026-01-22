"""
Pydantic schemas for Price POS.
Request and response models for price_pos API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Price POS Schemas
# ============================================================================

class PricePosBase(BaseModel):
    """Base schema for PricePos"""
    state: str = Field(..., max_length=100, description="State name")
    point_of_sale: str = Field(..., max_length=255, description="Point of sale / store name")
    promoter: str = Field(..., max_length=255, description="Promoter name")
    pricelist: str = Field(..., max_length=255, description="Pricelist name")


class PricePosCreate(PricePosBase):
    """Schema for creating a new price POS entry"""
    pass


class PricePosUpdate(BaseModel):
    """Schema for updating a price POS entry"""
    state: Optional[str] = Field(None, max_length=100, description="State name")
    point_of_sale: Optional[str] = Field(None, max_length=255, description="Point of sale / store name")
    promoter: Optional[str] = Field(None, max_length=255, description="Promoter name")
    pricelist: Optional[str] = Field(None, max_length=255, description="Pricelist name")


class PricePosResponse(PricePosBase):
    """Schema for price POS response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PricePosBulkCreate(BaseModel):
    """Schema for bulk creating price POS entries"""
    entries: List[PricePosCreate] = Field(..., description="List of price POS entries to create")


# ============================================================================
# Query and Filter Schemas
# ============================================================================

class PricePosFilter(BaseModel):
    """Schema for filtering price POS entries"""
    state: Optional[str] = Field(None, description="Filter by state name")
    point_of_sale: Optional[str] = Field(None, description="Filter by point of sale (partial match)")
    promoter: Optional[str] = Field(None, description="Filter by promoter name (partial match)")
    pricelist: Optional[str] = Field(None, description="Filter by pricelist name (partial match)")
    search: Optional[str] = Field(None, description="Search across all fields")


class PricePosListResponse(BaseModel):
    """Schema for paginated list of price POS entries"""
    items: List[PricePosResponse]
    total: int
    skip: int
    limit: int


# ============================================================================
# Statistics Schemas
# ============================================================================

class PricePosStats(BaseModel):
    """Schema for price POS statistics"""
    total_entries: int
    unique_states: int
    unique_pos: int
    unique_promoters: int
    unique_pricelists: int


class PricePosGroupByState(BaseModel):
    """Schema for grouping by state"""
    state: str
    count: int


class PricePosGroupByPromoter(BaseModel):
    """Schema for grouping by promoter"""
    promoter: str
    count: int


class PricePosGroupByPricelist(BaseModel):
    """Schema for grouping by pricelist"""
    pricelist: str
    count: int


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
