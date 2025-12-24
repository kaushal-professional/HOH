"""
POS Entry Pydantic schemas for request/response validation.
"""

from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from uuid import UUID


# Request Schemas (matching frontend payload)
class ProductRequest(BaseModel):
    """Schema for individual product within a barcode page"""
    barcode: str
    product: str
    price: Decimal
    article_code: Optional[int] = None
    weight_code: Optional[str] = None
    barcode_format: Optional[str] = None
    store_name: Optional[str] = None
    pricelist: Optional[str] = None
    weight: Optional[Decimal] = None
    gst: Optional[Decimal] = None
    price_with_gst: Optional[Decimal] = None


class BarcodeScannedPageRequest(BaseModel):
    """Schema for barcode scanned page"""
    page_number: int
    store_name: Optional[str] = None
    products: List[ProductRequest]
    total_count: int


class GeneralNoteRequest(BaseModel):
    """Schema for general note information"""
    date: str = Field(..., description="Date in format DD-MM-YYYY")
    promoter_name: str
    barcode_scanned_pages: List[BarcodeScannedPageRequest]
    total_barcode_count: int
    note_text: Optional[str] = None


class ItemRequest(BaseModel):
    """Schema for summary items"""
    ykey: str
    product: str
    quantity: Decimal
    price: Decimal
    unit: str
    discount: Decimal


class POSEntryRequest(BaseModel):
    """Main POS Entry request schema"""
    items: List[ItemRequest]
    general_note: GeneralNoteRequest
    store_name: str


# Response Schemas
class BarcodeProductResponse(BaseModel):
    """Response schema for barcode product"""
    id: UUID
    barcode: str
    product: str
    price: Decimal
    article_code: Optional[int]
    weight_code: Optional[str]
    barcode_format: Optional[str]
    store_name: Optional[str]
    pricelist: Optional[str]
    weight: Optional[Decimal]
    gst: Optional[Decimal]
    price_with_gst: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True


class BarcodeResponse(BaseModel):
    """Response schema for barcode page"""
    id: UUID
    page_number: int
    count: int
    products: List[BarcodeProductResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class ItemResponse(BaseModel):
    """Response schema for item"""
    id: UUID
    ykey: str
    product: str
    quantity: Decimal
    price: Decimal
    unit: str
    discount: Decimal
    store_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class GeneralNoteResponse(BaseModel):
    """Response schema for general note"""
    id: UUID
    note_date: date
    promoter_name: str
    note: Optional[str]
    store_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class POSEntryResponse(BaseModel):
    """Main POS Entry response schema"""
    general_note: GeneralNoteResponse
    items: List[ItemResponse]
    barcodes: List[BarcodeResponse]
    total_items: int
    total_barcode_pages: int
    total_products_scanned: int

    class Config:
        from_attributes = True
