"""
Pydantic schemas for Product, State, Store, and Store-Product mapping.
Request and response models for API endpoints.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


# ============================================================================
# Product Schemas
# ============================================================================

class ProductBase(BaseModel):
    """Base schema for Product"""
    product_id: str = Field(..., max_length=20, description="Product Y KEY (e.g., Y0520)")
    product_type: str = Field(..., max_length=100, description="Product type (e.g., Almond, Cashew)")
    product_description: str = Field(..., description="Detailed product description")
    is_active: bool = Field(default=True, description="Whether product is active")


class ProductCreate(ProductBase):
    """Schema for creating a new product"""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product"""
    product_type: Optional[str] = Field(None, max_length=100)
    product_description: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    """Schema for product response"""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# State Schemas
# ============================================================================

class StateBase(BaseModel):
    """Base schema for State"""
    state_name: str = Field(..., max_length=100, description="State name (e.g., Delhi, Karnataka)")
    state_code: Optional[str] = Field(None, max_length=10, description="State code (e.g., DL, KA)")
    is_active: bool = Field(default=True, description="Whether state is active")


class StateCreate(StateBase):
    """Schema for creating a new state"""
    pass


class StateUpdate(BaseModel):
    """Schema for updating a state"""
    state_name: Optional[str] = Field(None, max_length=100)
    state_code: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None


class StateResponse(StateBase):
    """Schema for state response"""
    state_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Store Schemas
# ============================================================================

class StoreBase(BaseModel):
    """Base schema for Store"""
    store_name: str = Field(..., max_length=255, description="Store name")
    store_code: Optional[str] = Field(None, max_length=20, description="Store code")
    email: Optional[str] = Field(None, max_length=255, description="Store email (links to user table)")
    state_id: int = Field(..., description="State ID this store belongs to")
    is_active: bool = Field(default=True, description="Whether store is active")


class StoreCreate(StoreBase):
    """Schema for creating a new store"""
    pass


class StoreUpdate(BaseModel):
    """Schema for updating a store"""
    store_name: Optional[str] = Field(None, max_length=255)
    store_code: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    state_id: Optional[int] = None
    is_active: Optional[bool] = None


class StoreResponse(StoreBase):
    """Schema for store response"""
    store_id: int
    created_at: datetime
    updated_at: datetime
    state: Optional[StateResponse] = None

    class Config:
        from_attributes = True


class StoreDetailResponse(StoreResponse):
    """Schema for detailed store response with product count"""
    total_products: int = Field(0, description="Total number of products available")


# ============================================================================
# Store-Product Mapping Schemas
# ============================================================================

class StoreProductBase(BaseModel):
    """Base schema for StoreProduct mapping"""
    store_id: int = Field(..., description="Store ID")
    product_id: str = Field(..., max_length=20, description="Product ID (Y KEY)")
    is_available: bool = Field(default=True, description="Product availability status")


class StoreProductCreate(StoreProductBase):
    """Schema for creating a new store-product mapping"""
    pass


class StoreProductBulkCreate(BaseModel):
    """Schema for bulk creating store-product mappings"""
    store_id: int = Field(..., description="Store ID")
    product_ids: List[str] = Field(..., description="List of product IDs to add")
    is_available: bool = Field(default=True, description="Availability status for all products")


class StoreProductUpdate(BaseModel):
    """Schema for updating store-product mapping"""
    is_available: Optional[bool] = None


class StoreProductResponse(StoreProductBase):
    """Schema for store-product response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StoreProductDetailResponse(BaseModel):
    """Schema for detailed store-product response with product info"""
    id: int
    store_id: int
    product_id: str
    is_available: bool
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


# ============================================================================
# State-Product Mapping Schemas
# ============================================================================

class StateProductBase(BaseModel):
    """Base schema for StateProduct mapping"""
    state_id: int = Field(..., description="State ID")
    product_id: str = Field(..., max_length=20, description="Product ID (Y KEY)")


class StateProductCreate(StateProductBase):
    """Schema for creating a new state-product mapping"""
    pass


class StateProductBulkCreate(BaseModel):
    """Schema for bulk creating state-product mappings"""
    state_id: int = Field(..., description="State ID")
    product_ids: List[str] = Field(..., description="List of product IDs to add")


class StateProductResponse(StateProductBase):
    """Schema for state-product response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# User Product Query Schemas
# ============================================================================

class ProductAvailabilityCheck(BaseModel):
    """Schema for checking product availability"""
    product_id: str = Field(..., description="Product ID to check")
    is_available: bool = Field(..., description="Whether product is available for user's store")


class UserProductsResponse(BaseModel):
    """Schema for user's available products"""
    store_info: StoreDetailResponse
    products: List[ProductResponse]
    total_count: int = Field(..., description="Total number of products")


class ProductTypeResponse(BaseModel):
    """Schema for product types list"""
    product_types: List[str] = Field(..., description="List of unique product types")
    count: int = Field(..., description="Number of unique types")


# ============================================================================
# Pagination and Filter Schemas
# ============================================================================

class PaginationParams(BaseModel):
    """Schema for pagination parameters"""
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of records to return")


class ProductFilterParams(BaseModel):
    """Schema for product filtering"""
    product_type: Optional[str] = Field(None, description="Filter by product type")
    search: Optional[str] = Field(None, description="Search in product description")
    is_active: Optional[bool] = Field(None, description="Filter by active status")


# ============================================================================
# Success/Error Response Schemas
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None


class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    success: bool
    created_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    errors: List[str] = []
