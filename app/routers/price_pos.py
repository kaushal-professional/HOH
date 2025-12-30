"""
API Router for Price POS endpoints.
Full CRUD operations for the price_pos table.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.services.price_pos_repository import PricePosRepository
from app.schemas.price_pos import (
    PricePosCreate,
    PricePosUpdate,
    PricePosResponse,
    PricePosBulkCreate,
    PricePosFilter,
    PricePosListResponse,
    PricePosStats,
    PricePosGroupByState,
    PricePosGroupByPromoter,
    PricePosGroupByPricelist,
    SuccessResponse,
    BulkOperationResponse,
)

router = APIRouter(prefix="/price-pos", tags=["Price POS (Point of Sale Mapping)"])
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
# CREATE ENDPOINTS
# ============================================================================

@router.post("/", response_model=PricePosResponse, status_code=status.HTTP_201_CREATED)
def create_price_pos(
    entry: PricePosCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Create a new price POS mapping entry.

    **Required fields:**
    - state: State name
    - point_of_sale: Point of sale / store name
    - promoter: Promoter name
    - pricelist: Pricelist name
    """
    db_entry = PricePosRepository.create(db, entry)
    return PricePosResponse.model_validate(db_entry)


@router.post("/bulk", response_model=BulkOperationResponse)
def bulk_create_price_pos(
    bulk_create: PricePosBulkCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Bulk create multiple price POS mapping entries.

    Useful for importing data from Excel or CSV files.
    """
    result = PricePosRepository.bulk_create(db, bulk_create.entries)
    return BulkOperationResponse(**result)


# ============================================================================
# READ ENDPOINTS
# ============================================================================

@router.get("/", response_model=PricePosListResponse)
def get_all_price_pos(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    point_of_sale: Optional[str] = Query(None, description="Filter by point of sale (partial match)"),
    promoter: Optional[str] = Query(None, description="Filter by promoter name (partial match)"),
    pricelist: Optional[str] = Query(None, description="Filter by pricelist name (partial match)"),
    search: Optional[str] = Query(None, description="Search across all fields"),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price POS mapping entries with optional filters and pagination.

    **Query Parameters:**
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 20, max: 100)
    - state: Filter by state name
    - point_of_sale: Filter by point of sale (partial match supported)
    - promoter: Filter by promoter name (partial match supported)
    - pricelist: Filter by pricelist name (partial match supported)
    - search: Search across all fields
    """
    filters = PricePosFilter(
        state=state,
        point_of_sale=point_of_sale,
        promoter=promoter,
        pricelist=pricelist,
        search=search
    )

    entries, total = PricePosRepository.get_all(db, skip, limit, filters)

    return PricePosListResponse(
        items=[PricePosResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{entry_id}", response_model=PricePosResponse)
def get_price_pos_by_id(
    entry_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a specific price POS mapping entry by ID.
    """
    entry = PricePosRepository.get_by_id(db, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price POS entry with ID {entry_id} not found"
        )
    return PricePosResponse.model_validate(entry)


@router.get("/by-state/{state}", response_model=PricePosListResponse)
def get_price_pos_by_state(
    state: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price POS mapping entries for a specific state.

    Shows all point of sale to pricelist mappings in this state.
    """
    entries, total = PricePosRepository.get_by_state(db, state, skip, limit)

    return PricePosListResponse(
        items=[PricePosResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-pos/{point_of_sale}", response_model=PricePosListResponse)
def get_price_pos_by_point_of_sale(
    point_of_sale: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price POS mapping entries for a specific point of sale.

    Shows pricelist mappings for this store.
    """
    entries, total = PricePosRepository.get_by_point_of_sale(db, point_of_sale, skip, limit)

    return PricePosListResponse(
        items=[PricePosResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-promoter/{promoter}", response_model=PricePosListResponse)
def get_price_pos_by_promoter(
    promoter: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price POS mapping entries for a specific promoter.

    Shows all stores managed by this promoter.
    """
    entries, total = PricePosRepository.get_by_promoter(db, promoter, skip, limit)

    return PricePosListResponse(
        items=[PricePosResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-pricelist/{pricelist}", response_model=PricePosListResponse)
def get_price_pos_by_pricelist(
    pricelist: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price POS mapping entries for a specific pricelist.

    Shows all stores using this pricelist.
    """
    entries, total = PricePosRepository.get_by_pricelist(db, pricelist, skip, limit)

    return PricePosListResponse(
        items=[PricePosResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


# ============================================================================
# UPDATE ENDPOINTS
# ============================================================================

@router.put("/{entry_id}", response_model=PricePosResponse)
def update_price_pos(
    entry_id: int,
    entry_update: PricePosUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Update a price POS mapping entry.

    You can update any of the fields: state, point_of_sale, promoter, pricelist.
    Only provide the fields you want to update.
    """
    updated_entry = PricePosRepository.update(db, entry_id, entry_update)
    if not updated_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price POS entry with ID {entry_id} not found"
        )
    return PricePosResponse.model_validate(updated_entry)


# ============================================================================
# DELETE ENDPOINTS
# ============================================================================

@router.delete("/{entry_id}", response_model=SuccessResponse)
def delete_price_pos(
    entry_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete a price POS mapping entry by ID.
    """
    success = PricePosRepository.delete(db, entry_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price POS entry with ID {entry_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"Price POS entry {entry_id} deleted successfully"
    )


@router.delete("/by-pos/{point_of_sale}", response_model=SuccessResponse)
def delete_price_pos_by_point_of_sale(
    point_of_sale: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete all price POS mapping entries for a specific point of sale.

    Deletes all mapping entries for the specified store.
    """
    success = PricePosRepository.delete_by_point_of_sale(db, point_of_sale)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entries found for point of sale '{point_of_sale}'"
        )
    return SuccessResponse(
        success=True,
        message=f"Deleted all entries for point of sale '{point_of_sale}'"
    )


# ============================================================================
# STATISTICS & ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/stats/overview", response_model=PricePosStats)
def get_price_pos_statistics(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get overall statistics for the price_pos table.

    Returns:
    - Total number of entries
    - Number of unique states
    - Number of unique points of sale
    - Number of unique promoters
    - Number of unique pricelists
    """
    stats = PricePosRepository.get_statistics(db)
    return PricePosStats(**stats)


@router.get("/stats/by-state", response_model=List[PricePosGroupByState])
def get_entries_grouped_by_state(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by state with counts.

    Shows how many POS mapping entries exist for each state.
    """
    results = PricePosRepository.group_by_state(db)
    return [PricePosGroupByState(**r) for r in results]


@router.get("/stats/by-promoter", response_model=List[PricePosGroupByPromoter])
def get_entries_grouped_by_promoter(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by promoter with counts.

    Shows how many stores each promoter manages.
    """
    results = PricePosRepository.group_by_promoter(db)
    return [PricePosGroupByPromoter(**r) for r in results]


@router.get("/stats/by-pricelist", response_model=List[PricePosGroupByPricelist])
def get_entries_grouped_by_pricelist(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by pricelist with counts.

    Shows how many stores use each pricelist.
    """
    results = PricePosRepository.group_by_pricelist(db)
    return [PricePosGroupByPricelist(**r) for r in results]


@router.get("/lists/states", response_model=List[str])
def get_unique_states(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique state names.
    """
    return PricePosRepository.get_unique_states(db)


@router.get("/lists/pos", response_model=List[str])
def get_unique_point_of_sales(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique point of sale names.
    """
    return PricePosRepository.get_unique_point_of_sales(db)


@router.get("/lists/promoters", response_model=List[str])
def get_unique_promoters(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique promoter names.
    """
    return PricePosRepository.get_unique_promoters(db)


@router.get("/lists/pricelists", response_model=List[str])
def get_unique_pricelists(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique pricelist names.
    """
    return PricePosRepository.get_unique_pricelists(db)
