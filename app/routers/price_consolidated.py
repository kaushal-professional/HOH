"""
API Router for Price Consolidated endpoints.
Full CRUD operations for the price_consolidated table.
"""

from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.services.price_consolidated_repository import PriceConsolidatedRepository
from app.schemas.price_consolidated import (
    PriceConsolidatedCreate,
    PriceConsolidatedUpdate,
    PriceConsolidatedResponse,
    PriceConsolidatedBulkCreate,
    PriceConsolidatedFilter,
    PriceConsolidatedListResponse,
    PriceWithGSTResponse,
    PriceConsolidatedStats,
    PriceConsolidatedGroupByPricelist,
    PriceConsolidatedGroupByProduct,
    PriceLookupRequest,
    PriceLookupResponse,
    SuccessResponse,
    BulkOperationResponse,
)

router = APIRouter(prefix="/price-consolidated", tags=["Price Consolidated (Product Pricing)"])
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
# Helper function to calculate price with GST
# ============================================================================

def calculate_price_with_gst(entry) -> PriceWithGSTResponse:
    """Calculate price with GST for display"""
    price_with_gst = None
    if entry.price and entry.gst is not None:
        price_with_gst = float(entry.price) + (float(entry.price) * float(entry.gst))

    return PriceWithGSTResponse(
        id=entry.id,
        pricelist=entry.pricelist,
        product=entry.product,
        price=entry.price,
        gst=entry.gst,
        price_with_gst=round(price_with_gst, 2) if price_with_gst else None,
        created_at=entry.created_at,
        updated_at=entry.updated_at
    )


# ============================================================================
# CREATE ENDPOINTS
# ============================================================================

@router.post("/", response_model=PriceConsolidatedResponse, status_code=status.HTTP_201_CREATED)
def create_price(
    entry: PriceConsolidatedCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Create a new price entry.

    **Required fields:**
    - pricelist: Pricelist or store name
    - product: Product name
    - price: Product price (without GST)
    - gst: GST percentage (optional, e.g., 0.05 for 5%, 0.18 for 18%)
    """
    db_entry = PriceConsolidatedRepository.create(db, entry)
    return PriceConsolidatedResponse.model_validate(db_entry)


@router.post("/bulk", response_model=BulkOperationResponse)
def bulk_create_prices(
    bulk_create: PriceConsolidatedBulkCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Bulk create or update multiple price entries.

    If a product-pricelist combination already exists, it will be updated.
    Useful for importing data from Excel or CSV files.
    """
    result = PriceConsolidatedRepository.bulk_create(db, bulk_create.entries)
    return BulkOperationResponse(**result)


# ============================================================================
# READ ENDPOINTS
# ============================================================================

@router.get("/", response_model=PriceConsolidatedListResponse)
def get_all_prices(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    pricelist: Optional[str] = Query(None, description="Filter by pricelist (partial match)"),
    product: Optional[str] = Query(None, description="Filter by product name (partial match)"),
    min_price: Optional[Decimal] = Query(None, description="Minimum price filter", ge=0),
    max_price: Optional[Decimal] = Query(None, description="Maximum price filter", ge=0),
    has_gst: Optional[bool] = Query(None, description="Filter by GST presence"),
    search: Optional[str] = Query(None, description="Search across all fields"),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price entries with optional filters and pagination.

    **Query Parameters:**
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 20, max: 100)
    - pricelist: Filter by pricelist name (partial match supported)
    - product: Filter by product name (partial match supported)
    - min_price: Minimum price filter
    - max_price: Maximum price filter
    - has_gst: Filter entries with/without GST (true=has GST, false=no GST)
    - search: Search across pricelist and product fields
    """
    filters = PriceConsolidatedFilter(
        pricelist=pricelist,
        product=product,
        min_price=min_price,
        max_price=max_price,
        has_gst=has_gst,
        search=search
    )

    entries, total = PriceConsolidatedRepository.get_all(db, skip, limit, filters)

    return PriceConsolidatedListResponse(
        items=[PriceConsolidatedResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{entry_id}", response_model=PriceWithGSTResponse)
def get_price_by_id(
    entry_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a specific price entry by ID, with calculated price including GST.
    """
    entry = PriceConsolidatedRepository.get_by_id(db, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price entry with ID {entry_id} not found"
        )
    return calculate_price_with_gst(entry)


@router.get("/by-pricelist/{pricelist}", response_model=PriceConsolidatedListResponse)
def get_prices_by_pricelist(
    pricelist: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price entries for a specific pricelist.

    Shows all products and their prices in this pricelist.
    """
    entries, total = PriceConsolidatedRepository.get_by_pricelist(db, pricelist, skip, limit)

    return PriceConsolidatedListResponse(
        items=[PriceConsolidatedResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-product/{product}", response_model=PriceConsolidatedListResponse)
def get_prices_by_product(
    product: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all price entries for a specific product across all pricelists.

    Shows price variations for the same product across different stores.
    """
    entries, total = PriceConsolidatedRepository.get_by_product(db, product, skip, limit)

    return PriceConsolidatedListResponse(
        items=[PriceConsolidatedResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-price-range/", response_model=PriceConsolidatedListResponse)
def get_products_by_price_range(
    min_price: Decimal = Query(..., description="Minimum price", ge=0),
    max_price: Decimal = Query(..., description="Maximum price", ge=0),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all products within a specific price range.

    **Query Parameters:**
    - min_price: Minimum price (required)
    - max_price: Maximum price (required)
    """
    entries, total = PriceConsolidatedRepository.get_products_by_price_range(
        db, min_price, max_price, skip, limit
    )

    return PriceConsolidatedListResponse(
        items=[PriceConsolidatedResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.post("/lookup", response_model=PriceLookupResponse)
def lookup_price(
    request: PriceLookupRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Lookup price for a product, optionally filtered by pricelist.

    Returns all matching price entries with calculated GST.
    """
    entries = PriceConsolidatedRepository.lookup_price(db, request.product, request.pricelist)

    if not entries:
        return PriceLookupResponse(
            found=False,
            entries=[],
            message=f"No price found for product '{request.product}'" +
                    (f" in pricelist '{request.pricelist}'" if request.pricelist else "")
        )

    return PriceLookupResponse(
        found=True,
        entries=[calculate_price_with_gst(e) for e in entries],
        message=f"Found {len(entries)} price(s) for product '{request.product}'" +
                (f" in pricelist '{request.pricelist}'" if request.pricelist else "")
    )


# ============================================================================
# UPDATE ENDPOINTS
# ============================================================================

@router.put("/{entry_id}", response_model=PriceConsolidatedResponse)
def update_price(
    entry_id: int,
    entry_update: PriceConsolidatedUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Update a price entry.

    You can update any of the fields: pricelist, product, price, gst.
    Only provide the fields you want to update.
    """
    updated_entry = PriceConsolidatedRepository.update(db, entry_id, entry_update)
    if not updated_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price entry with ID {entry_id} not found"
        )
    return PriceConsolidatedResponse.model_validate(updated_entry)


# ============================================================================
# DELETE ENDPOINTS
# ============================================================================

@router.delete("/{entry_id}", response_model=SuccessResponse)
def delete_price(
    entry_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete a price entry by ID.
    """
    success = PriceConsolidatedRepository.delete(db, entry_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price entry with ID {entry_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"Price entry {entry_id} deleted successfully"
    )


@router.delete("/by-pricelist/{pricelist}", response_model=SuccessResponse)
def delete_prices_by_pricelist(
    pricelist: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete all price entries for a specific pricelist.

    Deletes all product prices in the specified pricelist.
    """
    success = PriceConsolidatedRepository.delete_by_pricelist(db, pricelist)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entries found for pricelist '{pricelist}'"
        )
    return SuccessResponse(
        success=True,
        message=f"Deleted all entries for pricelist '{pricelist}'"
    )


@router.delete("/by-product/{product}", response_model=SuccessResponse)
def delete_prices_by_product(
    product: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete all price entries for a specific product across all pricelists.
    """
    success = PriceConsolidatedRepository.delete_by_product(db, product)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entries found for product '{product}'"
        )
    return SuccessResponse(
        success=True,
        message=f"Deleted all entries for product '{product}'"
    )


# ============================================================================
# STATISTICS & ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/stats/overview", response_model=PriceConsolidatedStats)
def get_price_statistics(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get overall statistics for the price_consolidated table.

    Returns:
    - Total number of entries
    - Number of unique pricelists
    - Number of unique products
    - Average, minimum, and maximum prices
    - Number of entries with GST
    """
    stats = PriceConsolidatedRepository.get_statistics(db)
    return PriceConsolidatedStats(**stats)


@router.get("/stats/by-pricelist", response_model=List[PriceConsolidatedGroupByPricelist])
def get_entries_grouped_by_pricelist(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by pricelist with counts and average price.

    Shows how many products exist in each pricelist and their average price.
    """
    results = PriceConsolidatedRepository.group_by_pricelist(db)
    return [PriceConsolidatedGroupByPricelist(**r) for r in results]


@router.get("/stats/by-product", response_model=List[PriceConsolidatedGroupByProduct])
def get_entries_grouped_by_product(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by product with min, max, and average prices.

    Shows price variations for each product across different pricelists.
    """
    results = PriceConsolidatedRepository.group_by_product(db)
    return [PriceConsolidatedGroupByProduct(**r) for r in results]


@router.get("/lists/pricelists", response_model=List[str])
def get_unique_pricelists(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique pricelist names.
    """
    return PriceConsolidatedRepository.get_unique_pricelists(db)


@router.get("/lists/products", response_model=List[str])
def get_unique_products(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique product names.
    """
    return PriceConsolidatedRepository.get_unique_products(db)
