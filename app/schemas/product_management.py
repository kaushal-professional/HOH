"""
Pydantic schemas for comprehensive product management.
Combines product, promoter, store assignments, and pricing.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Product Management Schemas (Products + Promoters + Pricing + Store Assignment)
# ============================================================================

class PromoterAssignmentBase(BaseModel):
    """Base schema for promoter assignment (article_codes table)"""
    article_code: Optional[int] = Field(None, description="Article code for the product")
    promoter: str = Field(..., max_length=255, description="Promoter name")


class PromoterAssignmentCreate(BaseModel):
    """Schema for creating promoter assignment"""
    article_code: int = Field(..., description="Article code for the product (required for creation)")
    promoter: str = Field(..., max_length=255, description="Promoter name")


class PromoterAssignmentResponse(PromoterAssignmentBase):
    """Schema for promoter assignment response"""
    id: int
    products: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PriceInfo(BaseModel):
    """Schema for price information"""
    pricelist: str = Field(..., max_length=255, description="Pricelist/Store name")
    price: float = Field(..., ge=0, description="Product price")
    gst: Optional[float] = Field(None, ge=0, le=1, description="GST percentage (0.05 for 5%)")


class PriceInfoResponse(PriceInfo):
    """Schema for price info response"""
    id: int
    product: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StoreAssignmentInfo(BaseModel):
    """Schema for store assignment information"""
    store_id: int = Field(..., description="Store ID")
    store_name: str = Field(..., description="Store name")
    is_available: bool = Field(True, description="Product availability")


class StoreAssignmentInfoResponse(StoreAssignmentInfo):
    """Schema for store assignment response with promoter info"""
    id: int
    product_id: str
    state_name: Optional[str] = None
    promoters: List[str] = Field(default=[], description="Promoters assigned to this store")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductManagementCreate(BaseModel):
    """Schema for creating a product with all assignments"""
    # Product info
    product_id: str = Field(..., max_length=20, description="Product Y KEY")
    product_type: str = Field(..., max_length=100, description="Product type")
    product_description: str = Field(..., description="Product description")
    is_active: bool = Field(default=True, description="Product active status")

    # Promoter assignments (article codes)
    # NOTE: When stores are assigned, promoters will be automatically determined
    # from the store-promoter mapping. Manual promoter assignments override this.
    promoter_assignments: Optional[List[PromoterAssignmentCreate]] = Field(
        default=None,
        description="List of promoter assignments for this product (optional, auto-assigned from stores)"
    )

    # Price information
    prices: Optional[List[PriceInfo]] = Field(
        default=None,
        description="List of prices for different pricelists/stores"
    )

    # Store assignments (primary way to assign products)
    # Promoters are automatically linked via store -> promoter mapping
    store_ids: Optional[List[int]] = Field(
        default=None,
        description="List of store IDs to assign this product to (promoters auto-linked)"
    )

    # Flag to auto-create article codes for store-promoter combinations
    auto_create_article_codes: bool = Field(
        default=False,
        description="Auto-create article codes for store-promoter combinations"
    )

    # Base article code for auto-generation (if auto_create_article_codes is True)
    base_article_code: Optional[int] = Field(
        default=None,
        description="Base article code for auto-generation (incremented per promoter)"
    )


class ProductManagementUpdate(BaseModel):
    """Schema for updating product management"""
    product_type: Optional[str] = Field(None, max_length=100)
    product_description: Optional[str] = None
    is_active: Optional[bool] = None

    # Note: Promoter assignments, prices, and store assignments are updated separately
    # via dedicated endpoints to avoid complexity


class ProductManagementResponse(BaseModel):
    """Schema for comprehensive product management response"""
    # Product info
    product_id: str
    product_type: str
    product_description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Related data
    promoter_assignments: List[PromoterAssignmentResponse] = Field(
        default=[],
        description="Promoter assignments for this product"
    )
    prices: List[PriceInfoResponse] = Field(
        default=[],
        description="Prices across different pricelists"
    )
    store_assignments: List[StoreAssignmentInfoResponse] = Field(
        default=[],
        description="Store assignments for this product"
    )

    class Config:
        from_attributes = True


class ProductManagementListResponse(BaseModel):
    """Schema for paginated product list"""
    products: List[ProductManagementResponse]
    total: int
    skip: int
    limit: int


# ============================================================================
# Promoter Assignment Management Schemas
# ============================================================================

class PromoterAssignmentUpdateRequest(BaseModel):
    """Schema for updating promoter assignment"""
    promoter: Optional[str] = Field(None, max_length=255)


class BulkPromoterAssignmentCreate(BaseModel):
    """Schema for bulk promoter assignment creation"""
    product_name: str = Field(..., description="Product name")
    assignments: List[PromoterAssignmentCreate] = Field(
        ...,
        description="List of promoter assignments to create"
    )


# ============================================================================
# Price Management Schemas
# ============================================================================

class PriceCreate(BaseModel):
    """Schema for creating a price entry"""
    pricelist: str = Field(..., max_length=255, description="Pricelist/Store name")
    product: str = Field(..., max_length=255, description="Product name")
    price: float = Field(..., ge=0, description="Product price")
    gst: Optional[float] = Field(None, ge=0, le=1, description="GST percentage")


class PriceUpdate(BaseModel):
    """Schema for updating a price entry"""
    pricelist: Optional[str] = Field(None, max_length=255)
    product: Optional[str] = Field(None, max_length=255)
    price: Optional[float] = Field(None, ge=0)
    gst: Optional[float] = Field(None, ge=0, le=1)


class PriceResponse(BaseModel):
    """Schema for price response"""
    id: int
    pricelist: str
    product: str
    price: float
    gst: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
