"""
API Router for POS Data Retrieval endpoints.
Provides endpoints for fetching, downloading POS data from
general_notes, barcodes, barcode_products with store_product info.
"""

from typing import Optional
from datetime import date, datetime
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.services.pos_retrieval_repository import POSRetrievalRepository
from app.schemas.pos_retrieval import (
    POSDataItem,
    POSRetrievalResponse,
    POSDownloadResponse,
    POSDateRangeRequest,
)

router = APIRouter(prefix="/pos-retrieval", tags=["POS Data Retrieval"])
security = HTTPBearer()


# ============================================================================
# Authentication Helper
# ============================================================================

def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract and validate user email from JWT token"""
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        email = payload.get("email") or payload.get("sub")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: email not found"
            )

        return email
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}"
        )


# ============================================================================
# POS DATA RETRIEVAL ENDPOINTS
# ============================================================================

@router.get("/", response_model=POSRetrievalResponse)
def get_pos_data(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of records per page"),
    store_name: Optional[str] = Query(None, description="Filter by store name"),
    _: str = Depends(get_current_user_email)
):
    """
    Get paginated POS data.

    Returns POS entries with the following fields:
    - **date**: Note date from general_notes
    - **general_note**: Note text
    - **store_name**: Store name
    - **ykey**: Y-Key from store_product table
    - **product_name**: Product name
    - **unit_of_measurement**: Unit of measure from store_product
    - **quantity**: Quantity/Weight
    - **unit_price**: Unit price excluding tax
    - **taxes**: GST/Tax amount
    - **price_excluding_tax**: Price excluding tax
    - **price_including_tax**: Price including tax
    - **created_at**: Full timestamp of record creation
    """
    data, total = POSRetrievalRepository.get_pos_data(
        db=db,
        page=page,
        page_size=page_size,
        store_name=store_name
    )

    total_pages = ceil(total / page_size) if total > 0 else 0

    return POSRetrievalResponse(
        data=[POSDataItem(**item) for item in data],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/download", response_model=POSDownloadResponse)
def download_pos_data(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10000, ge=1, description="Number of records per page"),
    store_name: Optional[str] = Query(None, description="Filter by store name"),
    _: str = Depends(get_current_user_email)
):
    """
    Download POS data with pagination.

    Returns paginated POS entries for export/download.
    Supports large page sizes for bulk downloads.
    """
    data, total = POSRetrievalRepository.get_pos_data(
        db=db,
        page=page,
        page_size=page_size,
        store_name=store_name
    )

    return POSDownloadResponse(
        data=[POSDataItem(**item) for item in data],
        total=total,
        downloaded_at=datetime.now()
    )


@router.get("/download/all", response_model=POSDownloadResponse)
def download_all_pos_data(
    db: Session = Depends(get_db),
    store_name: Optional[str] = Query(None, description="Filter by store name"),
    _: str = Depends(get_current_user_email)
):
    """
    Download all POS data (no pagination).

    Returns all POS entries for full export/download.
    Use with caution for large datasets.
    """
    data = POSRetrievalRepository.get_all_pos_data(
        db=db,
        store_name=store_name
    )

    return POSDownloadResponse(
        data=[POSDataItem(**item) for item in data],
        total=len(data),
        downloaded_at=datetime.now()
    )


@router.get("/download/date-range", response_model=POSDownloadResponse)
def download_pos_data_by_date_range(
    start_date: date = Query(..., description="Start date (inclusive, format: YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (inclusive, format: YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    store_name: Optional[str] = Query(None, description="Filter by store name"),
    _: str = Depends(get_current_user_email)
):
    """
    Download POS data within a date range.

    Filters by created_at timestamp (date portion only).
    The full timestamp is included in the response.

    - **start_date**: Start date (inclusive)
    - **end_date**: End date (inclusive)
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be less than or equal to end_date"
        )

    data = POSRetrievalRepository.get_pos_data_by_date_range(
        db=db,
        start_date=start_date,
        end_date=end_date,
        store_name=store_name
    )

    return POSDownloadResponse(
        data=[POSDataItem(**item) for item in data],
        total=len(data),
        downloaded_at=datetime.now()
    )


@router.get("/stores", response_model=dict)
def get_available_stores(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get list of all stores with POS data.

    Useful for populating store filter dropdowns.
    """
    stores = POSRetrievalRepository.get_available_stores(db)

    return {
        "stores": stores,
        "total": len(stores)
    }
