"""
Pydantic schemas for Store Product Flat table.
Request and response models for the store_product (singular) API endpoints.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Store Product Flat Schemas
# ============================================================================

class StoreProductFlatBase(BaseModel):
    """Base schema for StoreProductFlat"""
    ykey: str = Field(..., description="Product Y KEY (e.g., Y0520)")
    product_name: str = Field(..., description="Product name/description")
    store: str = Field(..., description="Store name")
    state: str = Field(..., description="State name")


class StoreProductFlatCreate(StoreProductFlatBase):
    """Schema for creating a new store product entry"""
    pass


class StoreProductFlatUpdate(BaseModel):
    """Schema for updating a store product entry"""
    ykey: Optional[str] = Field(None, description="Product Y KEY")
    product_name: Optional[str] = Field(None, description="Product name/description")
    store: Optional[str] = Field(None, description="Store name")
    state: Optional[str] = Field(None, description="State name")


class StoreProductFlatResponse(StoreProductFlatBase):
    """Schema for store product response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StoreProductFlatBulkCreate(BaseModel):
    """Schema for bulk creating store product entries"""
    entries: List[StoreProductFlatCreate] = Field(..., description="List of store product entries to create")


# ============================================================================
# Query and Filter Schemas
# ============================================================================

class StoreProductFlatFilter(BaseModel):
    """Schema for filtering store product entries"""
    ykey: Optional[str] = Field(None, description="Filter by product Y KEY")
    store: Optional[str] = Field(None, description="Filter by store name (partial match)")
    state: Optional[str] = Field(None, description="Filter by state name")
    search: Optional[str] = Field(None, description="Search in product name")


class StoreProductFlatListResponse(BaseModel):
    """Schema for paginated list of store products"""
    items: List[StoreProductFlatResponse]
    total: int
    skip: int
    limit: int


# ============================================================================
# Statistics Schemas
# ============================================================================

class StoreProductFlatStats(BaseModel):
    """Schema for store product statistics"""
    total_entries: int
    unique_ykeys: int
    unique_stores: int
    unique_states: int


class StoreProductFlatGroupByState(BaseModel):
    """Schema for grouping by state"""
    state: str
    count: int


class StoreProductFlatGroupByStore(BaseModel):
    """Schema for grouping by store"""
    store: str
    state: str
    count: int


class StoreProductFlatGroupByYKey(BaseModel):
    """Schema for grouping by YKEY"""
    ykey: str
    product_name: str
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
