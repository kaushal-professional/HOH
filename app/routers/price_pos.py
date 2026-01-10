"""
API Router for Price POS endpoints.
Full CRUD operations for the price_pos table.
"""

import time
import pandas as pd
from io import StringIO
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, Form, UploadFile
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
    CSVUploadResponse,
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

@router.post("/", response_model=BulkOperationResponse, status_code=status.HTTP_201_CREATED)
def create_price_pos(
    entries: List[PricePosCreate],
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Create one or multiple price POS mapping entries.

    **Accepts a list of entries with the following required fields:**
    - state: State name
    - point_of_sale: Point of sale / store name
    - promoter: Promoter name
    - pricelist: Pricelist name

    **Note:** Send as an array even for single entry: `[{...}]`
    """
    result = PricePosRepository.bulk_create(db, entries)
    return BulkOperationResponse(**result)


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


@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_bulk_create(
    file: UploadFile = File(..., description="CSV file with price POS mapping data"),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Upload CSV file to bulk create price POS mapping entries.

    **CSV Format:**
    Required headers (case-insensitive): state, point_of_sale, promoter, pricelist

    **Example CSV:**
    ```csv
    state,point_of_sale,promoter,pricelist
    Maharashtra,Smart Bazaar - Mumbai,Smart & Essentials Barcode,Smart Bazaar Price List
    Maharashtra,Star Bazaar - Thane,Star Bazaar Barcode,Star Bazaar Price List
    Karnataka,Food Square - Bangalore,Food Square Barcode,Food Square Price List
    ```

    **Parameters:**
    - file: CSV file upload (required)

    **Returns:**
    - Detailed response with counts of created/failed entries and any errors
    """
    start_time = time.time()

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file (.csv extension)"
        )

    try:
        # Read file content
        content = await file.read()

        # Check file size (10 MB limit)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 10 MB limit"
            )

        # Try to decode with UTF-8, fallback to latin-1
        try:
            content_str = content.decode('utf-8')
        except UnicodeDecodeError:
            content_str = content.decode('latin-1')

        # Parse CSV with pandas
        df = pd.read_csv(StringIO(content_str))

        # Check row limit
        if len(df) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV contains {len(df)} rows. Maximum allowed is 10,000 rows."
            )

        # Map column names (case-insensitive, handle variations)
        column_mapping = {}
        for col in df.columns:
            col_lower = col.strip().lower()
            if col_lower in ['state', 'state_name', 'state name']:
                column_mapping[col] = 'state'
            elif col_lower in ['point_of_sale', 'point of sale', 'pos', 'store', 'store_name']:
                column_mapping[col] = 'point_of_sale'
            elif col_lower in ['promoter', 'promoter_name', 'promoter name']:
                column_mapping[col] = 'promoter'
            elif col_lower in ['pricelist', 'price list', 'price_list', 'pricelist_name']:
                column_mapping[col] = 'pricelist'

        # Rename columns
        df.rename(columns=column_mapping, inplace=True)

        # Check required columns
        required_columns = ['state', 'point_of_sale', 'promoter', 'pricelist']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )

        # Clean data - strip whitespace, handle NaN
        for col in required_columns:
            df[col] = df[col].fillna('').astype(str).str.strip()

        # Validate and create entries
        created_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        from app.models.price_pos import PricePos

        for idx, row in df.iterrows():
            # Skip empty rows
            if all(row[col] == '' for col in required_columns):
                skipped_count += 1
                continue

            # Validate required fields
            missing_fields = [col for col in required_columns if not row[col]]
            if missing_fields:
                errors.append({
                    "row": idx + 2,
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "data": row.to_dict()
                })
                failed_count += 1
                continue

            try:
                # Create new entry
                db_price_pos = PricePos(
                    state=row['state'],
                    point_of_sale=row['point_of_sale'],
                    promoter=row['promoter'],
                    pricelist=row['pricelist']
                )
                db.add(db_price_pos)
                created_count += 1

            except Exception as e:
                errors.append({
                    "row": idx + 2,
                    "error": f"Error creating entry: {str(e)}",
                    "data": row.to_dict()
                })
                failed_count += 1

        # Commit all changes
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database commit failed: {str(e)}"
            )

        processing_time = time.time() - start_time

        return CSVUploadResponse(
            success=failed_count == 0,
            total_rows=len(df),
            created_count=created_count,
            updated_count=0,
            skipped_count=skipped_count,
            failed_count=failed_count,
            errors=errors,
            warnings=[],
            processing_time_seconds=round(processing_time, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV file: {str(e)}"
        )


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
