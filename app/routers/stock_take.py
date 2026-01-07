"""
API Router for Stock Take, Open Stock, and Close Stock endpoints.
Full CRUD operations for the stock take management system.
"""

from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.models.stock_take import StockTake
from app.services.stock_take_repository import (
    StockTakeRepository,
    OpenStockRepository,
    CloseStockRepository,
)
from app.schemas.stock_take import (
    StockTakeCreate, StockTakeUpdate, StockTakeResponse, StockTakeSummaryResponse, StockTakeListResponse,
    OpenStockCreate, OpenStockUpdate, OpenStockResponse, OpenStockBulkCreate,
    CloseStockCreate, CloseStockUpdate, CloseStockResponse, CloseStockBulkCreate, CloseStockByStore,
)

class StockTakeListSummaryResponse(BaseModel):
    """Schema for paginated stock take list with full details"""
    items: List[StockTakeSummaryResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True

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
# STOCK TAKE ENDPOINTS
# ============================================================================

@router.post("/", response_model=StockTakeResponse, status_code=status.HTTP_201_CREATED)
def create_stock_take(
    stock_take: StockTakeCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new stock take with optional open stock entries.

    - **store_name**: Name of the store
    - **start_date**: Stock take start date
    - **end_date**: Stock take end date (optional)
    - **open_stock_entries**: List of opening stock entries (optional)
    """
    db_stock_take = StockTakeRepository.create(db, stock_take)

    # Add counts
    response = StockTakeResponse.model_validate(db_stock_take)
    response.open_stock_count = len(db_stock_take.open_stocks)
    response.close_stock_count = len(db_stock_take.close_stocks)

    return response


@router.get("/", response_model=StockTakeListSummaryResponse)
def list_stock_takes(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    store_name: Optional[str] = Query(None, description="Filter by store name"),
    stock_status: Optional[str] = Query(None, description="Filter by status (active/completed)"),
    start_date_from: Optional[date] = Query(None, description="Filter by start date from"),
    start_date_to: Optional[date] = Query(None, description="Filter by start date to")
):
    """
    List all stock takes with optional filters and pagination.
    Includes all open_stock and close_stock entries.

    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return
    - **store_name**: Filter by store name (partial match)
    - **stock_status**: Filter by status (active or completed)
    - **start_date_from**: Filter by start date from
    - **start_date_to**: Filter by start date to
    """
    from app.models.pos_entry import BarcodeProduct
    from sqlalchemy import func, cast, Date
    
    stock_takes, total = StockTakeRepository.get_all(
        db, skip, limit, store_name, stock_status, start_date_from, start_date_to
    )

    # Build response with full stock details and pos_weight
    items = []
    for st in stock_takes:
        response = StockTakeSummaryResponse.model_validate(st)
        response.open_stock_count = len(st.open_stocks)
        response.close_stock_count = len(st.close_stocks)
        
        # Get barcode products for this store and date to fetch pos_weight
        barcode_weights = db.query(
            BarcodeProduct.product,
            func.sum(BarcodeProduct.weight).label('total_weight')
        ).filter(
            BarcodeProduct.store_name == st.store_name,
            cast(BarcodeProduct.created_at, Date) == st.start_date
        ).group_by(BarcodeProduct.product).all()
        
        # Create a dict for quick lookup
        weight_map = {item.product: float(item.total_weight) if item.total_weight else None for item in barcode_weights}
        
        # Add pos_weight to open_stocks
        for open_stock in response.open_stocks:
            open_stock.pos_weight = weight_map.get(open_stock.product_name)
        
        # Add pos_weight to close_stocks
        for close_stock in response.close_stocks:
            close_stock.pos_weight = weight_map.get(close_stock.product_name)
        
        items.append(response)

    return StockTakeListSummaryResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{stock_take_id}", response_model=StockTakeResponse)
def get_stock_take(
    stock_take_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a specific stock take by ID.

    - **stock_take_id**: UUID of the stock take
    """
    db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )

    response = StockTakeResponse.model_validate(db_stock_take)
    response.open_stock_count = len(db_stock_take.open_stocks)
    response.close_stock_count = len(db_stock_take.close_stocks)

    return response


@router.put("/{stock_take_id}", response_model=StockTakeResponse)
def update_stock_take(
    stock_take_id: UUID,
    stock_take_update: StockTakeUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a stock take.

    - **stock_take_id**: UUID of the stock take
    - **store_name**: Updated store name (optional)
    - **start_date**: Updated start date (optional)
    - **end_date**: Updated end date (optional)
    - **status**: Updated status (optional)
    """
    db_stock_take = StockTakeRepository.update(db, stock_take_id, stock_take_update)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )

    response = StockTakeResponse.model_validate(db_stock_take)
    response.open_stock_count = len(db_stock_take.open_stocks)
    response.close_stock_count = len(db_stock_take.close_stocks)

    return response


@router.delete("/{stock_take_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock_take(
    stock_take_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete a stock take (cascade deletes all open and close stock entries).

    - **stock_take_id**: UUID of the stock take
    """
    success = StockTakeRepository.delete(db, stock_take_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )
    return None


@router.get("/{stock_take_id}/summary", response_model=StockTakeSummaryResponse)
def get_stock_take_summary(
    stock_take_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get complete stock take summary including all open and close stock entries.

    - **stock_take_id**: UUID of the stock take
    """
    db_stock_take = StockTakeRepository.get_summary(db, stock_take_id)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )

    response = StockTakeSummaryResponse.model_validate(db_stock_take)
    response.open_stock_count = len(db_stock_take.open_stocks)
    response.close_stock_count = len(db_stock_take.close_stocks)

    return response


@router.post("/{stock_take_id}/complete", response_model=StockTakeResponse)
def complete_stock_take(
    stock_take_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Mark a stock take as completed and set end_date to today if not already set.

    - **stock_take_id**: UUID of the stock take
    """
    db_stock_take = StockTakeRepository.complete_stock_take(db, stock_take_id)
    if not db_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )

    response = StockTakeResponse.model_validate(db_stock_take)
    response.open_stock_count = len(db_stock_take.open_stocks)
    response.close_stock_count = len(db_stock_take.close_stocks)

    return response


# ============================================================================
# OPEN STOCK ENDPOINTS
# ============================================================================

@router.post("/{stock_take_id}/open-stock", response_model=List[OpenStockResponse], status_code=status.HTTP_201_CREATED)
def create_open_stock_bulk(
    stock_take_id: UUID,
    bulk_data: OpenStockBulkCreate,
    db: Session = Depends(get_db)
):
    """
    Bulk create or update open stock entries for a stock take.
    If an entry already exists (same product + promoter), it will be updated.

    - **stock_take_id**: UUID of the stock take
    - **entries**: List of open stock entries to create/update
    """
    db_entries = OpenStockRepository.bulk_create(db, stock_take_id, bulk_data.entries)
    return [OpenStockResponse.model_validate(entry) for entry in db_entries]


@router.get("/{stock_take_id}/open-stock", response_model=List[OpenStockResponse])
def get_open_stock_by_stock_take(
    stock_take_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get all open stock entries for a specific stock take.

    - **stock_take_id**: UUID of the stock take
    """
    # Verify stock take exists
    stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
    if not stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )

    entries = OpenStockRepository.get_by_stock_take(db, stock_take_id)
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
# CLOSE STOCK ENDPOINTS
# ============================================================================

@router.post("/{stock_take_id}/close-stock", response_model=List[CloseStockResponse], status_code=status.HTTP_201_CREATED)
def create_close_stock_bulk(
    stock_take_id: UUID,
    bulk_data: CloseStockBulkCreate,
    db: Session = Depends(get_db)
):
    """
    Bulk create or update close stock entries for a stock take.
    If an entry already exists (same product + promoter), it will be updated.

    - **stock_take_id**: UUID of the stock take
    - **entries**: List of close stock entries to create/update
    """
    db_entries = CloseStockRepository.bulk_create(db, stock_take_id, bulk_data.entries)
    return [CloseStockResponse.model_validate(entry) for entry in db_entries]


@router.get("/{stock_take_id}/close-stock", response_model=List[CloseStockResponse])
def get_close_stock_by_stock_take(
    stock_take_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get all close stock entries for a specific stock take.

    - **stock_take_id**: UUID of the stock take
    """
    # Verify stock take exists
    stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
    if not stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock take with ID {stock_take_id} not found"
        )

    entries = CloseStockRepository.get_by_stock_take(db, stock_take_id)
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


@router.post("/close-stock-by-store", response_model=List[CloseStockResponse], status_code=status.HTTP_201_CREATED)
def create_close_stock_by_store(
    data: CloseStockByStore,
    db: Session = Depends(get_db)
):
    """
    Add close stock entries by store name - automatically finds the active stock take and validates products.

    - **store_name**: Name of the store (must match exactly)
    - **entries**: List of close stock entries to create/update

    This endpoint will:
    1. Find the active stock take for the given store name (using UUID internally)
    2. Validate that products being closed exist in the opening stock
    3. Add the close stock entries to that stock take
    4. Return the created/updated close stock entries
    """
    from app.models.stock_take import OpenStock

    # Step 1: Find active stock take for this store using store_name
    active_stock_take = db.query(StockTake).filter(
        StockTake.store_name == data.store_name,
        StockTake.status == 'active'
    ).first()

    if not active_stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active stock take found for store: {data.store_name}"
        )

    # Step 2: Get all open stock entries for this stock take (linked via UUID)
    open_stock_entries = db.query(OpenStock).filter(
        OpenStock.stock_take_id == active_stock_take.stock_take_id
    ).all()

    # Create a set of (product_name, promoter_name) tuples from open stock for validation
    open_products = {
        (entry.product_name, entry.promoter_name)
        for entry in open_stock_entries
    }

    # Step 3: Validate that all close stock products exist in open stock
    invalid_entries = []
    for entry in data.entries:
        product_key = (entry.product_name, entry.promoter_name)
        if product_key not in open_products:
            invalid_entries.append({
                "product_name": entry.product_name,
                "promoter_name": entry.promoter_name,
                "error": "Product not found in opening stock"
            })

    # If there are invalid entries, return a detailed error
    if invalid_entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Some products were not found in the opening stock",
                "invalid_entries": invalid_entries,
                "available_products": [
                    {
                        "product_name": entry.product_name,
                        "promoter_name": entry.promoter_name
                    }
                    for entry in open_stock_entries
                ]
            }
        )

    # Step 4: Add close stock entries to the stock take (linked via UUID)
    db_entries = CloseStockRepository.bulk_create(db, active_stock_take.stock_take_id, data.entries)

    # Step 5: Update end_date in stock_take table when close stock is recorded
    if not active_stock_take.end_date:
        from datetime import date
        active_stock_take.end_date = date.today()
        db.commit()
        db.refresh(active_stock_take)

    return [CloseStockResponse.model_validate(entry) for entry in db_entries]
