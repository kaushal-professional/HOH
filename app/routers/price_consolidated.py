"""
API Router for Price Consolidated endpoints.
Full CRUD operations for the price_consolidated table.
"""

import time
import pandas as pd
from io import StringIO
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, Form, UploadFile
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
    CSVUploadResponse,
    CSVUpdateResponse,
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


@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_bulk_create(
    file: UploadFile = File(..., description="CSV file with price data"),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Upload CSV file to bulk create price entries.

    **CSV Format:**
    Required headers (case-insensitive): pricelist, product, price, gst (optional)

    **Example CSV:**
    ```csv
    pricelist,product,price,gst
    Smart Bazaar,Almonds Non Pareil Running (25-29) Loose FG,1250.50,0.05
    Star Bazaar,Cashew W320 Loose FG,950.00,0.05
    Food Square,Pistachios Loose FG,1580.75,0.18
    ```

    **Parameters:**
    - file: CSV file upload (required)

    **Returns:**
    - Detailed response with counts of created/failed entries and any errors

    **Note:** If a product-pricelist combination already exists, it will be updated with new price/GST.
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
            if col_lower in ['pricelist', 'price list', 'price_list', 'store', 'store_name']:
                column_mapping[col] = 'pricelist'
            elif col_lower in ['product', 'product_name', 'product name', 'item']:
                column_mapping[col] = 'product'
            elif col_lower in ['price', 'amount', 'rate']:
                column_mapping[col] = 'price'
            elif col_lower in ['gst', 'tax', 'gst_percentage', 'gst percentage']:
                column_mapping[col] = 'gst'

        # Rename columns
        df.rename(columns=column_mapping, inplace=True)

        # Check required columns
        required_columns = ['pricelist', 'product', 'price']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )

        # Clean data - strip whitespace, handle NaN
        df['pricelist'] = df['pricelist'].fillna('').astype(str).str.strip()
        df['product'] = df['product'].fillna('').astype(str).str.strip()

        # Convert price to numeric
        df['price'] = pd.to_numeric(df['price'], errors='coerce')

        # Handle GST (optional column)
        if 'gst' in df.columns:
            df['gst'] = pd.to_numeric(df['gst'], errors='coerce')
        else:
            df['gst'] = pd.NA

        # Validate and create entries using existing bulk_create method
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        for idx, row in df.iterrows():
            # Skip empty rows
            if row['pricelist'] == '' and row['product'] == '' and pd.isna(row['price']):
                skipped_count += 1
                continue

            # Validate required fields
            missing_fields = []
            if not row['pricelist']:
                missing_fields.append('pricelist')
            if not row['product']:
                missing_fields.append('product')
            if pd.isna(row['price']) or row['price'] < 0:
                missing_fields.append('price')

            if missing_fields:
                errors.append({
                    "row": idx + 2,
                    "error": f"Missing or invalid required fields: {', '.join(missing_fields)}",
                    "data": row.to_dict()
                })
                failed_count += 1
                continue

            try:
                price_value = Decimal(str(row['price']))
                gst_value = None
                if not pd.isna(row['gst']):
                    gst_value = Decimal(str(row['gst']))
                    # Validate GST is between 0 and 1
                    if gst_value < 0 or gst_value > 1:
                        errors.append({
                            "row": idx + 2,
                            "error": f"GST must be between 0 and 1 (e.g., 0.05 for 5%), got {gst_value}",
                            "data": row.to_dict()
                        })
                        failed_count += 1
                        continue

                # Check if entry already exists
                from sqlalchemy import and_
                from app.models.price_consolidated import PriceConsolidated

                existing = db.query(PriceConsolidated).filter(
                    and_(
                        PriceConsolidated.product == row['product'],
                        PriceConsolidated.pricelist == row['pricelist']
                    )
                ).first()

                if existing:
                    # Update existing entry
                    existing.price = price_value
                    if gst_value is not None:
                        existing.gst = gst_value
                    updated_count += 1
                else:
                    # Create new entry
                    db_price = PriceConsolidated(
                        pricelist=row['pricelist'],
                        product=row['product'],
                        price=price_value,
                        gst=gst_value
                    )
                    db.add(db_price)
                    created_count += 1

            except Exception as e:
                errors.append({
                    "row": idx + 2,
                    "error": f"Error processing entry: {str(e)}",
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
            updated_count=updated_count,
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


@router.post("/update-csv", response_model=CSVUpdateResponse)
async def upload_csv_bulk_update(
    file: UploadFile = File(..., description="CSV file with price data to update"),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Upload CSV file to bulk update price entries with pricelist+product matching.

    **Matching Strategy:**
    1. Match by pricelist AND product (both fields required)
    2. If found, update price and/or gst
    3. If not found, record as error

    **CSV Format:**
    Headers (case-insensitive): pricelist, product, price (optional), gst (optional)

    **Note:** At least one of price or gst must be provided for update

    **Example CSV:**
    ```csv
    pricelist,product,price,gst
    Smart Bazaar,Almonds Non Pareil Running (25-29) Loose FG,1300.00,0.05
    Star Bazaar,Cashew W320 Loose FG,980.50,
    Food Square,Pistachios Loose FG,,0.12
    ```

    **Parameters:**
    - file: CSV file upload (required)

    **Returns:**
    - Detailed response with update statistics and matching information
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
            if col_lower in ['pricelist', 'price list', 'price_list', 'store', 'store_name']:
                column_mapping[col] = 'pricelist'
            elif col_lower in ['product', 'product_name', 'product name', 'item']:
                column_mapping[col] = 'product'
            elif col_lower in ['price', 'amount', 'rate']:
                column_mapping[col] = 'price'
            elif col_lower in ['gst', 'tax', 'gst_percentage', 'gst percentage']:
                column_mapping[col] = 'gst'

        # Rename columns
        df.rename(columns=column_mapping, inplace=True)

        # Check required columns for matching
        required_columns = ['pricelist', 'product']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns for matching: {', '.join(missing_columns)}"
            )

        # Clean data
        df['pricelist'] = df['pricelist'].fillna('').astype(str).str.strip()
        df['product'] = df['product'].fillna('').astype(str).str.strip()

        # Handle optional columns
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
        else:
            df['price'] = pd.NA

        if 'gst' in df.columns:
            df['gst'] = pd.to_numeric(df['gst'], errors='coerce')
        else:
            df['gst'] = pd.NA

        # Process updates
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        not_found_count = 0
        matched_by_pricelist_product = 0
        errors = []

        from sqlalchemy import and_
        from app.models.price_consolidated import PriceConsolidated

        for idx, row in df.iterrows():
            # Skip empty rows
            if row['pricelist'] == '' and row['product'] == '':
                skipped_count += 1
                continue

            # Validate minimum required fields
            if not row['pricelist'] or not row['product']:
                errors.append({
                    "row": idx + 2,
                    "error": "Missing required fields: pricelist and product are both required",
                    "data": row.to_dict()
                })
                failed_count += 1
                continue

            # Check that at least one update field is provided
            has_price = not pd.isna(row['price']) if 'price' in row else False
            has_gst = not pd.isna(row['gst']) if 'gst' in row else False

            if not has_price and not has_gst:
                errors.append({
                    "row": idx + 2,
                    "error": "At least one of price or gst must be provided for update",
                    "data": row.to_dict()
                })
                failed_count += 1
                continue

            try:
                # Match by pricelist AND product
                db_price = db.query(PriceConsolidated).filter(
                    and_(
                        PriceConsolidated.pricelist == row['pricelist'],
                        PriceConsolidated.product == row['product']
                    )
                ).first()

                if db_price:
                    matched_by_pricelist_product += 1

                    # Update fields if provided
                    if has_price:
                        price_value = Decimal(str(row['price']))
                        if price_value < 0:
                            errors.append({
                                "row": idx + 2,
                                "error": f"Price must be non-negative, got {price_value}",
                                "data": row.to_dict()
                            })
                            failed_count += 1
                            continue
                        db_price.price = price_value

                    if has_gst:
                        gst_value = Decimal(str(row['gst']))
                        if gst_value < 0 or gst_value > 1:
                            errors.append({
                                "row": idx + 2,
                                "error": f"GST must be between 0 and 1 (e.g., 0.05 for 5%), got {gst_value}",
                                "data": row.to_dict()
                            })
                            failed_count += 1
                            continue
                        db_price.gst = gst_value

                    updated_count += 1
                else:
                    # Not found
                    not_found_count += 1
                    errors.append({
                        "row": idx + 2,
                        "error": f"No matching record found for pricelist '{row['pricelist']}' and product '{row['product']}'",
                        "data": row.to_dict()
                    })

            except Exception as e:
                errors.append({
                    "row": idx + 2,
                    "error": f"Error updating entry: {str(e)}",
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

        return CSVUpdateResponse(
            success=failed_count == 0 and not_found_count == 0,
            total_rows=len(df),
            updated_count=updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            not_found_count=not_found_count,
            matched_by_pricelist_product=matched_by_pricelist_product,
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
