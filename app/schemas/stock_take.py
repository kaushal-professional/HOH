"""
Pydantic schemas for Stock Take, Open Stock, and Close Stock.
Request and response models for API endpoints.
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from uuid import UUID


# ============================================================================
# Open Stock Schemas
# ============================================================================

class OpenStockBase(BaseModel):
    """Base schema for Open Stock"""
    product_name: str = Field(..., max_length=255, description="Product name")
    promoter_name: str = Field(..., max_length=255, description="Promoter name")
    open_qty: float = Field(..., ge=0, description="Opening quantity")

    @validator('open_qty')
    def validate_quantity(cls, v):
        if v < 0:
            raise ValueError('Quantity must be non-negative')
        return v


class OpenStockCreate(OpenStockBase):
    """Schema for creating a new open stock entry"""
    pass


class OpenStockUpdate(BaseModel):
    """Schema for updating an open stock entry"""
    product_name: Optional[str] = Field(None, max_length=255)
    promoter_name: Optional[str] = Field(None, max_length=255)
    open_qty: Optional[float] = Field(None, ge=0)

    @validator('open_qty')
    def validate_quantity(cls, v):
        if v is not None and v < 0:
            raise ValueError('Quantity must be non-negative')
        return v


class OpenStockResponse(OpenStockBase):
    """Schema for open stock response"""
    id: int
    stock_take_id: UUID
    created_at: datetime
    updated_at: datetime
    pos_weight: Optional[float] = Field(None, description="Weight from POS barcode products")

    class Config:
        from_attributes = True


class OpenStockBulkCreate(BaseModel):
    """Schema for bulk creating open stock entries"""
    entries: List[OpenStockCreate] = Field(..., description="List of open stock entries")


# ============================================================================
# Close Stock Schemas
# ============================================================================

class CloseStockBase(BaseModel):
    """Base schema for Close Stock"""
    product_name: str = Field(..., max_length=255, description="Product name")
    promoter_name: str = Field(..., max_length=255, description="Promoter name")
    close_qty: float = Field(..., ge=0, description="Closing quantity")

    @validator('close_qty')
    def validate_quantity(cls, v):
        if v < 0:
            raise ValueError('Quantity must be non-negative')
        return v


class CloseStockCreate(CloseStockBase):
    """Schema for creating a new close stock entry"""
    pass


class CloseStockUpdate(BaseModel):
    """Schema for updating a close stock entry"""
    product_name: Optional[str] = Field(None, max_length=255)
    promoter_name: Optional[str] = Field(None, max_length=255)
    close_qty: Optional[float] = Field(None, ge=0)

    @validator('close_qty')
    def validate_quantity(cls, v):
        if v is not None and v < 0:
            raise ValueError('Quantity must be non-negative')
        return v


class CloseStockResponse(CloseStockBase):
    """Schema for close stock response"""
    id: int
    stock_take_id: UUID
    created_at: datetime
    updated_at: datetime
    pos_weight: Optional[float] = Field(None, description="Weight from POS barcode products")

    class Config:
        from_attributes = True


class CloseStockBulkCreate(BaseModel):
    """Schema for bulk creating close stock entries"""
    entries: List[CloseStockCreate] = Field(..., description="List of close stock entries")


class CloseStockByStore(BaseModel):
    """Schema for creating close stock by store name"""
    store_name: str = Field(..., max_length=255, description="Store name to find active stock take")
    entries: List[CloseStockCreate] = Field(..., description="List of close stock entries")


# ============================================================================
# Stock Take Schemas
# ============================================================================

class StockTakeBase(BaseModel):
    """Base schema for Stock Take"""
    store_name: str = Field(..., max_length=255, description="Store name")
    start_date: date = Field(..., description="Stock take start date")
    end_date: Optional[date] = Field(None, description="Stock take end date")

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be greater than or equal to start date')
        return v


class StockTakeCreate(StockTakeBase):
    """Schema for creating a new stock take"""
    open_stock_entries: Optional[List[OpenStockCreate]] = Field(None, description="Optional list of opening stock entries")


class StockTakeUpdate(BaseModel):
    """Schema for updating a stock take"""
    store_name: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and 'start_date' in values and values['start_date'] and v < values['start_date']:
            raise ValueError('End date must be greater than or equal to start date')
        return v


class StockTakeResponse(StockTakeBase):
    """Schema for stock take response"""
    stock_take_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    open_stock_count: int = Field(0, description="Count of open stock entries")
    close_stock_count: int = Field(0, description="Count of close stock entries")

    class Config:
        from_attributes = True


class StockTakeSummaryResponse(StockTakeResponse):
    """Schema for stock take summary with all stock entries"""
    open_stocks: List[OpenStockResponse] = Field([], description="List of open stock entries")
    close_stocks: List[CloseStockResponse] = Field([], description="List of close stock entries")

    class Config:
        from_attributes = True


class StockTakeListResponse(BaseModel):
    """Schema for paginated stock take list response"""
    items: List[StockTakeResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
