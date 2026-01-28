"""
API Router for Stock Take, Open Stock, and Close Stock endpoints.
Full CRUD operations for the stock take management system.
All operations are date-based.
"""

from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.services.stock_take_repository import (
    StockTakeRepository,
    OpenStockRepository,
    CloseStockRepository,
    StockTakeSummaryRepository,
    StockVarianceRepository,
)
from app.schemas.stock_take import (
    StockTakeCreate, StockTakeUpdate, StockTakeResponse, StockTakeListResponse,
    OpenStockCreate, OpenStockUpdate, OpenStockResponse,
    CloseStockCreate, CloseStockUpdate, CloseStockResponse,
    StockTakeSummaryResponse,
    StockVarianceItem,
    StockVarianceDownloadResponse,
)

router = APIRouter(prefix="/stock-takes", tags=["Stock Take Management"])
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
# STOCK TAKE ENDPOINTS (Simplified - store + date based)
# ============================================================================

@router.post("/", response_model=StockTakeResponse, status_code=status.HTTP_201_CREATED)
def create_stock_take(
    stock_take: StockTakeCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new stock take for a store and date.
    If one already exists for the same store and date, returns the existing one.

    - **store_name**: Name of the store
    - **stock_date**: Stock take date
    """
    db_stock_take = StockTakeRepository.create(db, stock_take)
    return StockTakeResponse.model_validate(db_stock_take)


@router.get("/", response_model=StockTakeListResponse)
def list_stock_takes(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    store_name: Optional[str] = Query(None, description="Filter by store name"),
    stock_status: Optional[str] = Query(None, description="Filter by status (active/completed)"),
    date_from: Optional[date] = Query(None, description="Filter by date from"),
    date_to: Optional[date] = Query(None, description="Filter by date to")
):
    """
    List all stock takes with optional filters and pagination.

    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return
    - **store_name**: Filter by store name (partial match)
    - **stock_status**: Filter by status (active or completed)
    - **date_from**: Filter by date from
    - **date_to**: Filter by date to
    """
    stock_takes, total = StockTakeRepository.get_all(
        db, skip, limit, store_name, stock_status, date_from, date_to
    )

    items = [StockTakeResponse.model_validate(st) for st in stock_takes]
    return StockTakeListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/by-store-date", response_model=StockTakeResponse)
def get_stock_take_by_store_and_date(
    store_name: str = Query(..., description="Store name"),
    stock_date: date = Query(..., description="Stock take date"),
    db: Session = Depends(get_db)
):
    """
    Get a stock take by store name and date.

    - **store_name**: Name of the store
    - **stock_date**: Stock take date
    """
    db_stock_take = StockTakeRepository.get_by_store_and_date(db, store_name, stock_date)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take not found for store '{store_name}' on date '{stock_date}'"
        )
    return StockTakeResponse.model_validate(db_stock_take)


# ============================================================================
# STOCK TAKE SUMMARY ENDPOINTS (Must be before /{stock_take_id} to avoid route conflicts)
# ============================================================================

@router.get("/summary", response_model=StockTakeSummaryResponse)
def get_stock_take_summary(
    store_name: str = Query(..., description="Store name to get summary for"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (created_at from open_stock)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (created_at from close_stock)"),
    db: Session = Depends(get_db)
):
    """
    Get a linked stock take summary for a specific store.

    This endpoint links open_stock and close_stock entries by store_name.
    - **store_name**: Name of the store (required)
    - **start_date**: Filter entries with created_at >= start_date (optional)
    - **end_date**: Filter entries with created_at <= end_date (optional)

    Returns:
    - **store_name**: The queried store name
    - **start_date**: Earliest created_at from open_stock entries for this store
    - **end_date**: Latest created_at from close_stock entries for this store
    - **open_stock_entries**: All open stock entries for this store
    - **close_stock_entries**: All close stock entries for this store
    """
    summary = StockTakeSummaryRepository.get_summary_by_store(
        db, store_name, start_date, end_date
    )
    return StockTakeSummaryResponse(**summary)


@router.get("/summary/stores", response_model=List[str])
def get_stores_with_stock(
    db: Session = Depends(get_db)
):
    """
    Get a list of all stores that have open or close stock entries.

    Returns a sorted list of unique store names.
    """
    return StockTakeSummaryRepository.get_all_stores_with_stock(db)


# ============================================================================
# STOCK VARIANCE REPORT ENDPOINTS
# ============================================================================

@router.get("/variance-report/download", response_model=StockVarianceDownloadResponse)
def download_all_stock_variance(
    db: Session = Depends(get_db)
):
    """
    Download all stock variance data from all stores.

    This endpoint returns all variance data for export/download without any filtering.

    Returns all products with:
    - **start_date**: Timestamp from open_stock created_at
    - **end_date**: Timestamp from close_stock created_at
    - **product**: Product name
    - **unit_of_measure**: Unit of measure from store_product table
    - **ykey**: Y-Key from store_product table
    - **open_qty**: Opening quantity
    - **close_qty**: Closing quantity
    - **difference_qty**: Absolute difference (|open_qty - close_qty|, always positive)
    - **pos_total_sale**: Total POS sale quantity for this product
    - **variance**: Difference Qty - POS Total Sale
    """
    data = StockVarianceRepository.get_all_variance_data(db=db)

    return StockVarianceDownloadResponse(
        start_date=None,
        end_date=None,
        data=[StockVarianceItem(**item) for item in data],
        total=len(data),
        downloaded_at=datetime.now()
    )


@router.get("/variance-report/download/date-range", response_model=StockVarianceDownloadResponse)
def download_stock_variance_by_date_range(
    start_date: datetime = Query(..., description="Start datetime (inclusive, format: YYYY-MM-DDTHH:MM:SS)"),
    end_date: datetime = Query(..., description="End datetime (inclusive, format: YYYY-MM-DDTHH:MM:SS)"),
    db: Session = Depends(get_db)
):
    """
    Download stock variance data within a date range.

    This endpoint filters data by created_at timestamps from open_stock and close_stock tables.

    - **start_date**: Start datetime inclusive (required, format: YYYY-MM-DDTHH:MM:SS)
    - **end_date**: End datetime inclusive (required, format: YYYY-MM-DDTHH:MM:SS)

    Returns products within the date range with:
    - **start_date**: Timestamp from open_stock created_at
    - **end_date**: Timestamp from close_stock created_at
    - **product**: Product name
    - **unit_of_measure**: Unit of measure from store_product table
    - **ykey**: Y-Key from store_product table
    - **open_qty**: Opening quantity
    - **close_qty**: Closing quantity
    - **difference_qty**: Absolute difference (|open_qty - close_qty|, always positive)
    - **pos_total_sale**: Total POS sale quantity for this product
    - **variance**: Difference Qty - POS Total Sale
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be less than or equal to end_date"
        )

    data = StockVarianceRepository.get_variance_data_by_date_range(
        db=db,
        start_date=start_date,
        end_date=end_date
    )

    return StockVarianceDownloadResponse(
        start_date=start_date,
        end_date=end_date,
        data=[StockVarianceItem(**item) for item in data],
        total=len(data),
        downloaded_at=datetime.now()
    )


@router.get("/{stock_take_id}", response_model=StockTakeResponse)
def get_stock_take(
    stock_take_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific stock take by ID.

    - **stock_take_id**: ID of the stock take
    """
    db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )
    return StockTakeResponse.model_validate(db_stock_take)


@router.put("/{stock_take_id}", response_model=StockTakeResponse)
def update_stock_take(
    stock_take_id: int,
    stock_take_update: StockTakeUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a stock take status.

    - **stock_take_id**: ID of the stock take
    - **status**: Updated status (optional)
    """
    db_stock_take = StockTakeRepository.update(db, stock_take_id, stock_take_update)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )
    return StockTakeResponse.model_validate(db_stock_take)


@router.delete("/{stock_take_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock_take(
    stock_take_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a stock take.

    - **stock_take_id**: ID of the stock take
    """
    success = StockTakeRepository.delete(db, stock_take_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )
    return None


@router.post("/{stock_take_id}/complete", response_model=StockTakeResponse)
def complete_stock_take(
    stock_take_id: int,
    db: Session = Depends(get_db)
):
    """
    Mark a stock take as completed.

    - **stock_take_id**: ID of the stock take
    """
    db_stock_take = StockTakeRepository.complete_stock_take(db, stock_take_id)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )
    return StockTakeResponse.model_validate(db_stock_take)


# ============================================================================
# OPEN STOCK ENDPOINTS (Date-based, independent of stock_take)
# ============================================================================

@router.post("/open-stock", response_model=List[OpenStockResponse], status_code=status.HTTP_201_CREATED)
def create_open_stock(
    data: OpenStockCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update open stock entries for a specific store and date.
    If an entry already exists (same store + date + product + promoter), it will be updated.

    - **store_name**: Name of the store
    - **open_date**: Date for the opening stock
    - **entries**: List of open stock entries to create/update
    """
    db_entries = OpenStockRepository.bulk_create(db, data.store_name, data.open_date, data.entries)
    return [OpenStockResponse.model_validate(entry) for entry in db_entries]


@router.get("/open-stock", response_model=List[OpenStockResponse])
def get_open_stock_by_store(
    store_name: str = Query(..., description="Store name"),
    open_date: Optional[date] = Query(None, description="Specific date to filter (if not provided, returns all dates)"),
    date_from: Optional[date] = Query(None, description="Filter by date from"),
    date_to: Optional[date] = Query(None, description="Filter by date to"),
    db: Session = Depends(get_db)
):
    """
    Get open stock entries for a store with optional date filters.

    - **store_name**: Name of the store (required)
    - **open_date**: Specific date to filter (optional)
    - **date_from**: Filter by date from (optional)
    - **date_to**: Filter by date to (optional)
    """
    if open_date:
        entries = OpenStockRepository.get_by_store_and_date(db, store_name, open_date)
    else:
        entries = OpenStockRepository.get_by_store(db, store_name, date_from, date_to)
    return [OpenStockResponse.model_validate(entry) for entry in entries]


@router.get("/open-stock/{id}", response_model=OpenStockResponse)
def get_open_stock(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific open stock entry by ID.

    - **id**: ID of the open stock entry
    """
    db_entry = OpenStockRepository.get_by_id(db, id)
    if not db_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Open stock entry with ID {id} not found"
        )
    return OpenStockResponse.model_validate(db_entry)


@router.put("/open-stock/{id}", response_model=OpenStockResponse)
def update_open_stock(
    id: int,
    open_stock_update: OpenStockUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a specific open stock entry.

    - **id**: ID of the open stock entry
    - **product_name**: Updated product name (optional)
    - **promoter_name**: Updated promoter name (optional)
    - **open_qty**: Updated opening quantity (optional)
    """
    db_entry = OpenStockRepository.update(db, id, open_stock_update)
    if not db_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Open stock entry with ID {id} not found"
        )
    return OpenStockResponse.model_validate(db_entry)


@router.delete("/open-stock/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_open_stock(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific open stock entry.

    - **id**: ID of the open stock entry
    """
    success = OpenStockRepository.delete(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Open stock entry with ID {id} not found"
        )
    return None


# ============================================================================
# CLOSE STOCK ENDPOINTS (Date-based, independent of stock_take)
# ============================================================================

@router.post("/close-stock", response_model=List[CloseStockResponse], status_code=status.HTTP_201_CREATED)
def create_close_stock(
    data: CloseStockCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update close stock entries for a specific store and date.
    If an entry already exists (same store + date + product + promoter), it will be updated.

    - **store_name**: Name of the store
    - **close_date**: Date for the closing stock
    - **entries**: List of close stock entries to create/update
    """
    db_entries = CloseStockRepository.bulk_create(db, data.store_name, data.close_date, data.entries)
    return [CloseStockResponse.model_validate(entry) for entry in db_entries]


@router.get("/close-stock", response_model=List[CloseStockResponse])
def get_close_stock_by_store(
    store_name: str = Query(..., description="Store name"),
    close_date: Optional[date] = Query(None, description="Specific date to filter (if not provided, returns all dates)"),
    date_from: Optional[date] = Query(None, description="Filter by date from"),
    date_to: Optional[date] = Query(None, description="Filter by date to"),
    db: Session = Depends(get_db)
):
    """
    Get close stock entries for a store with optional date filters.

    - **store_name**: Name of the store (required)
    - **close_date**: Specific date to filter (optional)
    - **date_from**: Filter by date from (optional)
    - **date_to**: Filter by date to (optional)
    """
    if close_date:
        entries = CloseStockRepository.get_by_store_and_date(db, store_name, close_date)
    else:
        entries = CloseStockRepository.get_by_store(db, store_name, date_from, date_to)
    return [CloseStockResponse.model_validate(entry) for entry in entries]


@router.get("/close-stock/{id}", response_model=CloseStockResponse)
def get_close_stock(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific close stock entry by ID.

    - **id**: ID of the close stock entry
    """
    db_entry = CloseStockRepository.get_by_id(db, id)
    if not db_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Close stock entry with ID {id} not found"
        )
    return CloseStockResponse.model_validate(db_entry)


@router.put("/close-stock/{id}", response_model=CloseStockResponse)
def update_close_stock(
    id: int,
    close_stock_update: CloseStockUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a specific close stock entry.

    - **id**: ID of the close stock entry
    - **product_name**: Updated product name (optional)
    - **promoter_name**: Updated promoter name (optional)
    - **close_qty**: Updated closing quantity (optional)
    """
    db_entry = CloseStockRepository.update(db, id, close_stock_update)
    if not db_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Close stock entry with ID {id} not found"
        )
    return CloseStockResponse.model_validate(db_entry)


@router.delete("/close-stock/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_close_stock(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific close stock entry.

    - **id**: ID of the close stock entry
    """
    success = CloseStockRepository.delete(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Close stock entry with ID {id} not found"
        )
    return None
