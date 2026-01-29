"""
Pydantic schemas for Stock Take, Open Stock, and Close Stock.
Request and response models for API endpoints.
"""

from datetime import date, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
from uuid import UUID


# ============================================================================
# Open Stock Schemas (Date-based, independent of stock_take)
# ============================================================================

class OpenStockEntryBase(BaseModel):
    """Base schema for a single Open Stock entry"""
    product_name: str = Field(..., max_length=255, description="Product name")
    promoter_name: str = Field(..., max_length=255, description="Promoter name")
    open_qty: float = Field(..., ge=0, description="Opening quantity")

    @validator('open_qty')
    def validate_quantity(cls, v):
        if v < 0:
            raise ValueError('Quantity must be non-negative')
        return v


class OpenStockCreate(BaseModel):
    """Schema for creating open stock entries (date-based)"""
    store_name: str = Field(..., max_length=255, description="Store name")
    open_date: date = Field(..., description="Opening date for the stock")
    entries: List[OpenStockEntryBase] = Field(..., description="List of open stock entries")


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


class OpenStockResponse(OpenStockEntryBase):
    """Schema for open stock response"""
    id: int
    store_name: str
    open_date: date
    created_at: datetime
    updated_at: datetime
    pos_weight: Optional[float] = Field(None, description="Weight from POS barcode products")

    class Config:
        from_attributes = True


# ============================================================================
# Close Stock Schemas (Date-based, independent of stock_take)
# ============================================================================

class CloseStockEntryBase(BaseModel):
    """Base schema for a single Close Stock entry"""
    product_name: str = Field(..., max_length=255, description="Product name")
    promoter_name: str = Field(..., max_length=255, description="Promoter name")
    close_qty: float = Field(..., ge=0, description="Closing quantity")

    @validator('close_qty')
    def validate_quantity(cls, v):
        if v < 0:
            raise ValueError('Quantity must be non-negative')
        return v


class CloseStockCreate(BaseModel):
    """Schema for creating close stock entries (date-based)"""
    store_name: str = Field(..., max_length=255, description="Store name")
    close_date: date = Field(..., description="Closing date for the stock")
    entries: List[CloseStockEntryBase] = Field(..., description="List of close stock entries")


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


class CloseStockResponse(CloseStockEntryBase):
    """Schema for close stock response"""
    id: int
    store_name: str
    close_date: date
    created_at: datetime
    updated_at: datetime
    pos_weight: Optional[float] = Field(None, description="Weight from POS barcode products")

    class Config:
        from_attributes = True


# ============================================================================
# Stock Take Schemas (Simplified - store + date based)
# ============================================================================

class StockTakeBase(BaseModel):
    """Base schema for Stock Take"""
    store_name: str = Field(..., max_length=255, description="Store name")
    stock_date: date = Field(..., description="Stock take date")


class StockTakeCreate(StockTakeBase):
    """Schema for creating a new stock take"""
    pass


class StockTakeUpdate(BaseModel):
    """Schema for updating a stock take"""
    status: Optional[str] = Field(None, max_length=50)


class StockTakeResponse(StockTakeBase):
    """Schema for stock take response"""
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

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


# ============================================================================
# Stock Take Summary Schemas (Linking open_stock and close_stock by date range)
# ============================================================================

class OpenStockSummaryItem(BaseModel):
    """Schema for open stock item in summary"""
    id: int
    product_name: str
    promoter_name: str
    open_qty: float
    open_date: date
    created_at: datetime

    class Config:
        from_attributes = True


class CloseStockSummaryItem(BaseModel):
    """Schema for close stock item in summary"""
    id: int
    product_name: str
    promoter_name: str
    close_qty: float
    close_date: date
    created_at: datetime

    class Config:
        from_attributes = True


class StockTakeSummaryResponse(BaseModel):
    """
    Schema for linked stock take summary.
    Links open_stock, close_stock, and POS sales by store_name and date range.
    - start_date: Earliest created_at from open_stock entries
    - end_date: Latest created_at from close_stock entries
    """
    store_name: str
    start_date: Optional[datetime] = Field(None, description="Earliest created_at from open_stock")
    end_date: Optional[datetime] = Field(None, description="Latest created_at from close_stock")
    open_stock_entries: List[OpenStockSummaryItem] = Field(default_factory=list)
    close_stock_entries: List[CloseStockSummaryItem] = Field(default_factory=list)
    pos_sales: Dict[str, float] = Field(default_factory=dict, description="POS sales by product {product_name: quantity}")
    total_open_stock: int = Field(0, description="Total number of open stock entries")
    total_close_stock: int = Field(0, description="Total number of close stock entries")

    class Config:
        from_attributes = True


# ============================================================================
# Stock Variance Report Schemas
# ============================================================================

class StockVarianceItem(BaseModel):
    """Schema for a single stock variance report item"""
    store_name: str = Field(..., description="Store name")
    start_date: date = Field(..., description="Start date (from open_stock created_at)")
    end_date: date = Field(..., description="End date (from close_stock created_at)")
    product: str = Field(..., description="Product name")
    unit_of_measure: Optional[str] = Field(None, description="Unit of measure from store_product table")
    ykey: Optional[str] = Field(None, description="Y-Key from store_product table")
    open_qty: float = Field(..., description="Opening quantity")
    close_qty: float = Field(..., description="Closing quantity")
    difference_qty: float = Field(..., description="Absolute difference between open and close qty (always positive)")
    pos_total_sale: float = Field(..., description="Total POS sale quantity for this product")
    variance: float = Field(..., description="Variance = Difference Qty - POS Total Sale")

    class Config:
        from_attributes = True


class StockVarianceDownloadResponse(BaseModel):
    """Response schema for stock variance report download"""
    start_date: Optional[date] = Field(None, description="Filter start date")
    end_date: Optional[date] = Field(None, description="Filter end date")
    data: List[StockVarianceItem] = Field(default_factory=list)
    total: int = Field(0, description="Total number of records")
    downloaded_at: datetime = Field(..., description="Timestamp when data was downloaded")

    class Config:
        from_attributes = True
