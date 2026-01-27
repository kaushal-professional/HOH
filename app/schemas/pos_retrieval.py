"""
POS Retrieval schemas for API responses.
"""

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID


class POSDataItem(BaseModel):
    """Single POS data item for retrieval"""
    id: UUID
    date: date_type = Field(..., description="Note date from general_notes")
    general_note: Optional[str] = Field(default=None, description="Note text from general_notes")
    store_name: Optional[str] = Field(default=None, description="Store name")
    ykey: Optional[str] = Field(default=None, description="Y-Key from store_product table")
    product_name: str = Field(..., description="Product name from barcode_products")
    unit_of_measurement: Optional[str] = Field(default=None, description="Unit of measure from store_product table")
    quantity: Optional[Decimal] = Field(default=None, description="Quantity/Weight")
    unit_price: Decimal = Field(..., description="Unit price excluding tax")
    gst_percentage: Optional[Decimal] = Field(default=None, description="GST percentage calculated from tax amount")
    price_excluding_tax: Decimal = Field(..., description="Price excluding tax")
    price_including_tax: Decimal = Field(..., description="Price including tax (calculated: price_excl * (1 + gst_percentage/100))")
    created_at: datetime = Field(..., description="Full timestamp of record creation")

    class Config:
        from_attributes = True


class POSRetrievalResponse(BaseModel):
    """Response for POS data retrieval with pagination"""
    data: List[POSDataItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class POSDownloadResponse(BaseModel):
    """Response for POS data download (all records)"""
    data: List[POSDataItem]
    total: int
    downloaded_at: datetime


class POSDateRangeRequest(BaseModel):
    """Request for date range based download"""
    start_date: date_type = Field(..., description="Start date (inclusive)")
    end_date: date_type = Field(..., description="End date (inclusive)")
