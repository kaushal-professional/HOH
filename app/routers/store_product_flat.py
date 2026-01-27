"""
API Router for Store Product Flat table endpoints.
Full CRUD operations for the store_product (singular) table.
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
from app.services.store_product_flat_repository import StoreProductFlatRepository
from app.schemas.store_product_flat import (
    StoreProductFlatCreate,
    StoreProductFlatUpdate,
    StoreProductFlatResponse,
    StoreProductFlatBulkCreate,
    StoreProductFlatFilter,
    StoreProductFlatListResponse,
    StoreProductFlatStats,
    StoreProductFlatGroupByState,
    StoreProductFlatGroupByStore,
    StoreProductFlatGroupByYKey,
    SuccessResponse,
    BulkOperationResponse,
    CSVUploadResponse,
)

router = APIRouter(prefix="/store-product", tags=["Store Product (Flat Table)"])
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

@router.post("/", response_model=StoreProductFlatResponse, status_code=status.HTTP_201_CREATED)
def create_store_product(
    entry: StoreProductFlatCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Create a new store product entry.

    **Required fields:**
    - ykey: Product Y KEY (e.g., Y0520)
    - product_name: Product name/description
    - store: Store name
    - state: State name
    """
    db_entry = StoreProductFlatRepository.create(db, entry)
    return StoreProductFlatResponse.model_validate(db_entry)


@router.post("/bulk", response_model=BulkOperationResponse)
def bulk_create_store_products(
    bulk_create: StoreProductFlatBulkCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Bulk create multiple store product entries.

    Useful for importing data from Excel or CSV files.
    """
    result = StoreProductFlatRepository.bulk_create(db, bulk_create.entries)
    return BulkOperationResponse(**result)


@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_bulk_create(
    file: UploadFile = File(..., description="CSV file with store product data"),
    upsert: bool = Form(True, description="Update existing entries or skip duplicates"),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Upload CSV file to bulk create/update store product entries.

    **CSV Format:**
    Required headers (case-insensitive): ykey, product_name, store, state

    **Example CSV:**
    ```csv
    ykey,product_name,store,state
    Y0520,Almonds Non Pareil Running (25-29) Loose FG,Food Square - Bandra,Maharashtra
    Y0521,Cashew W320 Loose FG,Reliance Smart - Thane,Maharashtra
    ```

    **Parameters:**
    - file: CSV file upload (required)
    - upsert: If True, update existing (ykey, store, state) combinations. If False, skip duplicates. (default: True)

    **Returns:**
    - Detailed response with counts of created/updated/failed entries and any errors
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
            if col_lower in ['ykey', 'y key', 'y-key']:
                column_mapping[col] = 'ykey'
            elif col_lower in ['product_name', 'product name', 'article', 'product']:
                column_mapping[col] = 'product_name'
            elif col_lower in ['store', 'store name', 'store_name']:
                column_mapping[col] = 'store'
            elif col_lower in ['state', 'state name', 'state_name']:
                column_mapping[col] = 'state'

        # Rename columns
        df.rename(columns=column_mapping, inplace=True)

        # Check required columns
        required_columns = ['ykey', 'product_name', 'store', 'state']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )

        # Clean data - strip whitespace, handle NaN
        for col in required_columns:
            df[col] = df[col].fillna('').astype(str).str.strip()

        # Validate and convert to Pydantic models
        entries = []
        errors = []
        skipped_count = 0

        for idx, row in df.iterrows():
            # Skip empty rows
            if all(row[col] == '' for col in required_columns):
                skipped_count += 1
                continue

            # Validate required fields
            missing_fields = [col for col in required_columns if not row[col]]
            if missing_fields:
                errors.append({
                    "row": idx + 2,  # +2 for header and 0-indexing
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "data": row.to_dict()
                })
                continue

            try:
                entry = StoreProductFlatCreate(
                    ykey=row['ykey'],
                    product_name=row['product_name'],
                    store=row['store'],
                    state=row['state']
                )
                entries.append(entry)
            except Exception as e:
                errors.append({
                    "row": idx + 2,
                    "error": f"Validation error: {str(e)}",
                    "data": row.to_dict()
                })

        # Process bulk create/update
        if upsert:
            result = StoreProductFlatRepository.bulk_upsert(db, entries)
        else:
            result = StoreProductFlatRepository.bulk_create(db, entries)

        # Merge errors from validation and database operations
        all_errors = errors + result.get('errors', [])

        processing_time = time.time() - start_time

        return CSVUploadResponse(
            success=len(all_errors) == 0,
            total_rows=len(df),
            created_count=result.get('created_count', 0),
            updated_count=result.get('updated_count', 0),
            skipped_count=skipped_count,
            failed_count=len(all_errors),
            errors=all_errors,
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

@router.get("/", response_model=StoreProductFlatListResponse)
def get_all_store_products(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    ykey: Optional[str] = Query(None, description="Filter by product YKEY"),
    store: Optional[str] = Query(None, description="Filter by store name (partial match)"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    search: Optional[str] = Query(None, description="Search in product name"),
    _: str = Depends(get_current_user_email)
):
    """
    Get all store product entries with optional filters and pagination.

    **Query Parameters:**
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 20, max: 100)
    - ykey: Filter by specific product YKEY
    - store: Filter by store name (partial match supported)
    - state: Filter by state name
    - search: Search in product name/description
    """
    filters = StoreProductFlatFilter(
        ykey=ykey,
        store=store,
        state=state,
        search=search
    )

    entries, total = StoreProductFlatRepository.get_all(db, skip, limit, filters)

    return StoreProductFlatListResponse(
        items=[StoreProductFlatResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{entry_id}", response_model=StoreProductFlatResponse)
def get_store_product_by_id(
    entry_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a specific store product entry by ID.
    """
    entry = StoreProductFlatRepository.get_by_id(db, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store product entry with ID {entry_id} not found"
        )
    return StoreProductFlatResponse.model_validate(entry)


@router.get("/by-ykey/{ykey}", response_model=StoreProductFlatListResponse)
def get_store_products_by_ykey(
    ykey: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all store product entries for a specific YKEY (product).

    Shows which stores carry this product.
    """
    entries, total = StoreProductFlatRepository.get_by_ykey(db, ykey, skip, limit)

    return StoreProductFlatListResponse(
        items=[StoreProductFlatResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-store/{store}", response_model=StoreProductFlatListResponse)
def get_store_products_by_store(
    store: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all store product entries for a specific store.

    Shows all products available at this store.
    """
    entries, total = StoreProductFlatRepository.get_by_store(db, store, skip, limit)

    return StoreProductFlatListResponse(
        items=[StoreProductFlatResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/by-state/{state}", response_model=StoreProductFlatListResponse)
def get_store_products_by_state(
    state: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    _: str = Depends(get_current_user_email)
):
    """
    Get all store product entries for a specific state.

    Shows all products available across all stores in this state.
    """
    entries, total = StoreProductFlatRepository.get_by_state(db, state, skip, limit)

    return StoreProductFlatListResponse(
        items=[StoreProductFlatResponse.model_validate(e) for e in entries],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/view/products", response_model=List[dict])
def get_products_by_store_and_state(
    store: str = Query(..., description="Store name"),
    state: str = Query(..., description="State name"),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get list of products (articles and ykeys) for a specific store and state.

    **Query Parameters:**
    - store: Store name (required)
    - state: State name (required)

    **Returns:** List of products with ykey and article (product_name)

    **Example:**
    ```
    GET /api/store-product/view/products?store=Food Square - Bandra&state=Maharashtra
    ```
    """
    entries, _ = StoreProductFlatRepository.get_by_store_and_state(db, store, state)

    # Return simplified list with just ykey and article
    return [
        {
            "ykey": entry.ykey,
            "article": entry.product_name
        }
        for entry in entries
    ]


# ============================================================================
# UPDATE ENDPOINTS
# ============================================================================

@router.put("/{entry_id}", response_model=StoreProductFlatResponse)
def update_store_product(
    entry_id: int,
    entry_update: StoreProductFlatUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Update a store product entry.

    You can update any of the fields: ykey, product_name, store, state.
    Only provide the fields you want to update.
    """
    updated_entry = StoreProductFlatRepository.update(db, entry_id, entry_update)
    if not updated_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store product entry with ID {entry_id} not found"
        )
    return StoreProductFlatResponse.model_validate(updated_entry)


# ============================================================================
# DELETE ENDPOINTS
# ============================================================================

@router.delete("/{entry_id}", response_model=SuccessResponse)
def delete_store_product(
    entry_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete a store product entry by ID.
    """
    success = StoreProductFlatRepository.delete(db, entry_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store product entry with ID {entry_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"Store product entry {entry_id} deleted successfully"
    )


@router.delete("/by-ykey-store/{ykey}/{store}", response_model=SuccessResponse)
def delete_store_product_by_ykey_and_store(
    ykey: str,
    store: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete store product entries by YKEY and store name.

    Deletes all entries matching the specific YKEY and store combination.
    """
    success = StoreProductFlatRepository.delete_by_ykey_and_store(db, ykey, store)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entries found for YKEY '{ykey}' at store '{store}'"
        )
    return SuccessResponse(
        success=True,
        message=f"Deleted entries for YKEY '{ykey}' at store '{store}'"
    )


# ============================================================================
# STATISTICS & ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/stats/overview", response_model=StoreProductFlatStats)
def get_store_product_statistics(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get overall statistics for the store_product table.

    Returns:
    - Total number of entries
    - Number of unique products (YKEYs)
    - Number of unique stores
    - Number of unique states
    """
    stats = StoreProductFlatRepository.get_statistics(db)
    return StoreProductFlatStats(**stats)


@router.get("/stats/by-state", response_model=List[StoreProductFlatGroupByState])
def get_entries_grouped_by_state(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by state with counts.

    Shows how many product entries exist for each state.
    """
    results = StoreProductFlatRepository.group_by_state(db)
    return [StoreProductFlatGroupByState(**r) for r in results]


@router.get("/stats/by-store", response_model=List[StoreProductFlatGroupByStore])
def get_entries_grouped_by_store(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by store with counts.

    Shows how many products each store carries.
    """
    results = StoreProductFlatRepository.group_by_store(db)
    return [StoreProductFlatGroupByStore(**r) for r in results]


@router.get("/stats/by-ykey", response_model=List[StoreProductFlatGroupByYKey])
def get_entries_grouped_by_ykey(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get entries grouped by YKEY (product) with counts.

    Shows how many stores carry each product.
    """
    results = StoreProductFlatRepository.group_by_ykey(db)
    return [StoreProductFlatGroupByYKey(**r) for r in results]


@router.get("/lists/ykeys", response_model=List[str])
def get_unique_ykeys(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique product YKEYs.
    """
    return StoreProductFlatRepository.get_unique_ykeys(db)


@router.get("/lists/stores", response_model=List[str])
def get_unique_stores(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique store names.
    """
    return StoreProductFlatRepository.get_unique_stores(db)


@router.get("/lists/states", response_model=List[str])
def get_unique_states(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a list of all unique state names.
    """
    return StoreProductFlatRepository.get_unique_states(db)
