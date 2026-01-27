"""
API Router for Article Code and Promoter endpoints.
Full CRUD operations for articles and promoters.
"""

import time
import pandas as pd
from io import StringIO
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.article_code import ArticleCode, Promoter
from app.models.price_consolidated import PriceConsolidated
from app.schemas.article_code import (
    ArticleCodeCreate, ArticleCodeUpdate, ArticleCodeResponse,
    PromoterCreate, PromoterUpdate, PromoterResponse,
    BarcodeScanRequest, BarcodeScanResponse, ArticleLookupRequest,
    BulkOperationResponse, CSVUploadResponse, CSVUpdateResponse
)
from app.services.excel_data_loader import excel_loader
from app.services.barcode_decoder import BarcodeDecoder

router = APIRouter(prefix="/article-codes", tags=["Article Codes & Promoters"])


# ============================================================================
# BARCODE SCAN ENDPOINT
# ============================================================================

@router.post("/barcode-scan", response_model=BarcodeScanResponse, status_code=status.HTTP_200_OK)
def scan_barcode(
    request: BarcodeScanRequest,
    db: Session = Depends(get_db)
):
    """
    Decode barcode text and retrieve product information including price with GST and weight.

    This endpoint:
    1. Accepts a barcode text/number directly (no image scanning)
    2. Decodes the barcode to extract article code and weight using BarcodeDecoder service
    3. Retrieves product and price information from the database

    - **barcode**: The barcode text/number (e.g., "8801234567890", "]C12600022496...")
    - **store_name**: The store name where scan occurred (e.g., "Food Square", "Reliance Smart")

    Returns:
    - Product name (from article_codes table)
    - Article code (extracted from barcode)
    - Store name and type (identified from barcode format)
    - Promoter name (from promoter table via point_of_sale -> article_codes)
    - Price (from price_consolidated table, without GST)
    - GST percentage (from price_consolidated table, e.g., 0.05 for 5%)
    - Price with GST (calculated as price + (price * gst))
    - Weight in kg (extracted from barcode)
    """
    # Validate barcode input
    if not request.barcode or not request.barcode.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode cannot be empty"
        )

    barcode_text = request.barcode.strip()
    store_name = request.store_name

    # Step 1: Decode the barcode to extract article code and weight using BarcodeDecoder service
    article_code, weight, store_type = BarcodeDecoder.decode(barcode_text)

    if not article_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to decode barcode: {barcode_text}. Please check the barcode format."
        )

    # Step 2: Determine promoter name
    # PRIORITY 1: Use actual store location from promoter table (most accurate)
    # PRIORITY 2: Fallback to barcode format mapping if store not found

    promoter_name = None

    # Try to get promoter from the actual store location first
    if store_name:
        promoter_record = db.query(Promoter).filter(
            Promoter.point_of_sale.ilike(f"%{store_name}%")
        ).first()

        if promoter_record:
            promoter_name = promoter_record.promoter

    # Fallback: Use barcode format to determine promoter if store lookup failed
    if not promoter_name:
        store_type_to_promoter = {
            "reliance_smart": "Smart & Essentials Barcode",
            "smart_alternative": "Smart Alternate Barcode",
            "reliance_fresh": "FP & Signature Barcode",
            "star_bazar": "Star Bazaar Barcode",
            "food_square": "Food Square Barcode",
            "rapsap": "Rapsap",
            "mrdpl": "Magson Barcode",
        }

        promoter_name = store_type_to_promoter.get(store_type)

        if not promoter_name:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unable to determine promoter. Store '{store_name}' not found in promoter table and barcode type '{store_type}' is unknown."
            )

    # Step 3: Get article name from article_codes table using promoter and article_code
    article_record = db.query(ArticleCode).filter(
        ArticleCode.article_codes == article_code,
        ArticleCode.promoter == promoter_name
    ).first()

    # Fallback: If not found with store's promoter, try barcode format's promoter
    if not article_record and store_name:
        # Get barcode format's promoter as fallback
        store_type_to_promoter = {
            "reliance_smart": "Smart & Essentials Barcode",
            "smart_alternative": "Smart Alternate Barcode",
            "reliance_fresh": "FP & Signature Barcode",
            "star_bazar": "Star Bazaar Barcode",
            "food_square": "Food Square Barcode",
            "rapsap": "Rapsap",
            "mrdpl": "Magson Barcode",
        }
        barcode_promoter = store_type_to_promoter.get(store_type)

        if barcode_promoter and barcode_promoter != promoter_name:
            article_record = db.query(ArticleCode).filter(
                ArticleCode.article_codes == article_code,
                ArticleCode.promoter == barcode_promoter
            ).first()

            if article_record:
                # Update promoter_name to the one that worked
                promoter_name = barcode_promoter

    if not article_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article code {article_code} not found for promoter '{promoter_name}' or any fallback promoters"
        )

    product_name = article_record.products

    # Step 4: Get price and GST from price_consolidated table using product name and pricelist
    # Map promoter names to pricelist names for accurate price lookup
    promoter_to_pricelist = {
        "Smart & Essentials Barcode": ["Smart Bazaar", "Essentials"],
        "Smart Alternate Barcode": ["Smart Bazaar"],
        "FP & Signature Barcode": ["Signature Plus", "FP JWD, Powai, 1MG"],
        "Star Bazaar Barcode": ["Star Bazaar"],
        "Food Square Barcode": ["Food Square"],
        "Rapsap": ["Rapsap"],
        "Magson Barcode": ["Magson"],
    }

    price = None
    gst = None
    price_with_gst = None
    pricelist = store_name  # Default to store_name

    # Get potential pricelist names for this promoter
    pricelist_names = promoter_to_pricelist.get(promoter_name, [])

    # Try to find price using promoter-to-pricelist mapping
    price_record = None
    if pricelist_names:
        for pricelist_name in pricelist_names:
            price_record = db.query(PriceConsolidated).filter(
                PriceConsolidated.product == product_name,
                PriceConsolidated.pricelist == pricelist_name
            ).first()
            if price_record:
                break

    # Fallback: try partial match with store_name if no price found
    if not price_record:
        price_record = db.query(PriceConsolidated).filter(
            PriceConsolidated.product == product_name
        ).first()

    if price_record:
        price = float(price_record.price)
        pricelist = price_record.pricelist  # Use actual pricelist name from database

        # Get GST if available and calculate price with GST
        if price_record.gst is not None:
            gst = float(price_record.gst)
            # Calculate price with GST: price + (price * gst_percentage)
            price_with_gst = round(price + (price * gst), 2)

    # Step 5: Format weight code and barcode format for frontend display
    weight_code = f"{int(weight * 1000):05d}" if weight else "00000"  # Format as 5-digit string
    barcode_format = store_type.replace("_", " ").title()  # e.g., "star_bazar" -> "Star Bazar"

    # Step 6: Return comprehensive product information
    return BarcodeScanResponse(
        product=product_name,
        article_code=article_code,
        store_name=store_name,
        store_type=store_type,
        promoter=promoter_name,
        pricelist=pricelist,
        price=price,
        gst=gst,
        price_with_gst=price_with_gst,
        weight=weight,
        weight_code=weight_code,
        barcode_format=barcode_format
    )


# ============================================================================
# ARTICLE LOOKUP ENDPOINT
# ============================================================================

@router.post("/article-lookup", response_model=BarcodeScanResponse, status_code=status.HTTP_200_OK)
def lookup_article_by_name(request: ArticleLookupRequest, db: Session = Depends(get_db)):
    """
    Lookup article by product name and retrieve product information including price with GST.

    This endpoint searches for a product by name and store, then retrieves price information
    from the database, similar to the barcode scan endpoint but without barcode decoding.

    - **article_name**: The product/article name (e.g., "Almonds Non Pareil Running (25-29) Loose FG")
    - **store_name**: The store name (e.g., "Reliance Smart Bazaar - Genesis Mall (FRDS)")

    Returns:
    - Product name
    - Article code (from article_codes table)
    - Store name
    - Promoter name (from promoter table via point_of_sale)
    - Price (from price_consolidated table, without GST)
    - GST percentage (from price_consolidated table, e.g., 0.05 for 5%)
    - Price with GST (calculated as price + (price * gst))
    - Weight defaults to None (no barcode to decode)
    """
    # Step 1: Determine promoter name from store
    promoter_name = None

    if request.store_name:
        promoter_record = db.query(Promoter).filter(
            Promoter.point_of_sale.ilike(f"%{request.store_name}%")
        ).first()

        if promoter_record:
            promoter_name = promoter_record.promoter

    if not promoter_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter not found for store: {request.store_name}"
        )

    # Step 2: Get article record by product name and promoter
    article_record = db.query(ArticleCode).filter(
        ArticleCode.products.ilike(f"%{request.article_name}%"),
        ArticleCode.promoter == promoter_name
    ).first()

    # Fallback: Try without promoter filter if not found
    if not article_record:
        article_record = db.query(ArticleCode).filter(
            ArticleCode.products.ilike(f"%{request.article_name}%")
        ).first()

        # Update promoter if found with different promoter
        if article_record:
            promoter_name = article_record.promoter

    if not article_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article '{request.article_name}' not found for store '{request.store_name}'"
        )

    product_name = article_record.products
    article_code = article_record.article_codes

    # Step 3: Get price and GST from price_consolidated table
    # Map promoter names to pricelist names for accurate price lookup
    promoter_to_pricelist = {
        "Smart & Essentials Barcode": ["Smart Bazaar", "Essentials"],
        "Smart Alternate Barcode": ["Smart Bazaar"],
        "FP & Signature Barcode": ["Signature Plus", "FP JWD, Powai, 1MG"],
        "Star Bazaar Barcode": ["Star Bazaar"],
        "Food Square Barcode": ["Food Square"],
        "Rapsap": ["Rapsap"],
        "Magson Barcode": ["Magson"],
    }

    price = None
    gst = None
    price_with_gst = None
    pricelist = request.store_name  # Default to store_name

    # Get potential pricelist names for this promoter
    pricelist_names = promoter_to_pricelist.get(promoter_name, [])

    # Try to find price using promoter-to-pricelist mapping
    price_record = None
    if pricelist_names:
        for pricelist_name in pricelist_names:
            price_record = db.query(PriceConsolidated).filter(
                PriceConsolidated.product == product_name,
                PriceConsolidated.pricelist == pricelist_name
            ).first()
            if price_record:
                break

    # Fallback: try any pricelist with the product
    if not price_record:
        price_record = db.query(PriceConsolidated).filter(
            PriceConsolidated.product == product_name
        ).first()

    if price_record:
        price = float(price_record.price)
        pricelist = price_record.pricelist  # Use actual pricelist name from database

        # Get GST if available and calculate price with GST
        if price_record.gst is not None:
            gst = float(price_record.gst)
            # Calculate price with GST: price + (price * gst_percentage)
            price_with_gst = round(price + (price * gst), 2)

    # Step 4: Return product information (no barcode, so no weight/store_type)
    return BarcodeScanResponse(
        product=product_name,
        article_code=article_code,
        store_name=request.store_name,
        store_type="manual_lookup",  # Indicate this was a manual lookup
        promoter=promoter_name,
        pricelist=pricelist,
        price=price,
        gst=gst,
        price_with_gst=price_with_gst,
        weight=None,  # No barcode to decode weight from
        weight_code="00000",  # Default weight code
        barcode_format="Manual Lookup"  # Indicate manual lookup
    )


# ============================================================================
# ARTICLE CODE CRUD ENDPOINTS
# ============================================================================

@router.get("/", response_model=List[ArticleCodeResponse])
def get_article_codes(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search by product name or promoter"),
    article_code: Optional[int] = Query(None, description="Filter by specific article code")
):
    """
    Get all article codes with optional filtering.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **search**: Search in product name or promoter
    - **article_code**: Filter by specific article code
    """
    query = db.query(ArticleCode)

    if article_code:
        query = query.filter(ArticleCode.article_codes == article_code)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ArticleCode.products.ilike(search_pattern),
                ArticleCode.promoter.ilike(search_pattern)
            )
        )

    article_codes = query.offset(skip).limit(limit).all()
    return article_codes


@router.get("/{article_code_id}", response_model=ArticleCodeResponse)
def get_article_code(
    article_code_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific article code by ID.
    """
    article = db.query(ArticleCode).filter(ArticleCode.id == article_code_id).first()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article code with ID {article_code_id} not found"
        )

    return article


@router.post("/", response_model=ArticleCodeResponse, status_code=status.HTTP_201_CREATED)
def create_article_code(
    article_code: ArticleCodeCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new article code.

    - **products**: Product name
    - **article_codes**: Article barcode number (must be unique)
    - **promoter**: Promoter name
    """
    # Check if article code already exists
    existing = db.query(ArticleCode).filter(
        ArticleCode.article_codes == article_code.article_codes
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Article code {article_code.article_codes} already exists"
        )

    # Create new article code
    db_article = ArticleCode(**article_code.model_dump())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)

    return db_article


@router.put("/{article_code_id}", response_model=ArticleCodeResponse)
def update_article_code(
    article_code_id: int,
    article_code_update: ArticleCodeUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing article code.

    - **products**: Product name (optional)
    - **article_codes**: Article barcode number (optional, must be unique)
    - **promoter**: Promoter name (optional)
    """
    # Find the article code
    db_article = db.query(ArticleCode).filter(ArticleCode.id == article_code_id).first()

    if not db_article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article code with ID {article_code_id} not found"
        )

    # If updating article code number, check for duplicates
    if article_code_update.article_codes is not None:
        existing = db.query(ArticleCode).filter(
            ArticleCode.article_codes == article_code_update.article_codes,
            ArticleCode.id != article_code_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Article code {article_code_update.article_codes} already exists"
            )

    # Update fields
    update_data = article_code_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_article, field, value)

    db.commit()
    db.refresh(db_article)

    return db_article


@router.delete("/{article_code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article_code(
    article_code_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an article code by ID.
    """
    db_article = db.query(ArticleCode).filter(ArticleCode.id == article_code_id).first()

    if not db_article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article code with ID {article_code_id} not found"
        )

    db.delete(db_article)
    db.commit()

    return None


# ============================================================================
# CSV BULK OPERATIONS
# ============================================================================

@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_bulk_create(
    file: UploadFile = File(..., description="CSV file with article code data"),
    db: Session = Depends(get_db)
):
    """
    Upload CSV file to bulk create article code entries.

    **CSV Format:**
    Required headers (case-insensitive): products, article_codes, promoter

    **Example CSV:**
    ```csv
    products,article_codes,promoter
    Almonds Non Pareil Running (25-29) Loose FG,30027,Smart & Essentials Barcode
    Cashew W320 Loose FG,30028,Smart & Essentials Barcode
    Pistachios Loose FG,30029,Star Bazaar Barcode
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
            if col_lower in ['products', 'product', 'product_name', 'product name']:
                column_mapping[col] = 'products'
            elif col_lower in ['article_codes', 'article_code', 'article code', 'barcode']:
                column_mapping[col] = 'article_codes'
            elif col_lower in ['promoter', 'promoter name', 'promoter_name']:
                column_mapping[col] = 'promoter'

        # Rename columns
        df.rename(columns=column_mapping, inplace=True)

        # Check required columns
        required_columns = ['products', 'article_codes', 'promoter']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )

        # Clean data - strip whitespace, handle NaN
        df['products'] = df['products'].fillna('').astype(str).str.strip()
        df['promoter'] = df['promoter'].fillna('').astype(str).str.strip()

        # Convert article_codes to integer, handling errors
        df['article_codes'] = pd.to_numeric(df['article_codes'], errors='coerce')

        # Validate and create entries
        created_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        for idx, row in df.iterrows():
            # Skip empty rows
            if row['products'] == '' and row['promoter'] == '' and pd.isna(row['article_codes']):
                skipped_count += 1
                continue

            # Validate required fields
            missing_fields = []
            if not row['products']:
                missing_fields.append('products')
            if pd.isna(row['article_codes']):
                missing_fields.append('article_codes')
            if not row['promoter']:
                missing_fields.append('promoter')

            if missing_fields:
                errors.append({
                    "row": idx + 2,
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "data": row.to_dict()
                })
                failed_count += 1
                continue

            try:
                article_code_value = int(row['article_codes'])

                # Check if article code already exists
                existing = db.query(ArticleCode).filter(
                    ArticleCode.article_codes == article_code_value
                ).first()

                if existing:
                    errors.append({
                        "row": idx + 2,
                        "error": f"Article code {article_code_value} already exists",
                        "data": row.to_dict()
                    })
                    failed_count += 1
                    continue

                # Create new article code
                db_article = ArticleCode(
                    products=row['products'],
                    article_codes=article_code_value,
                    promoter=row['promoter']
                )
                db.add(db_article)
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


@router.post("/update-csv", response_model=CSVUpdateResponse)
async def upload_csv_bulk_update(
    file: UploadFile = File(..., description="CSV file with article code data to update"),
    db: Session = Depends(get_db)
):
    """
    Upload CSV file to bulk update article code entries with smart matching.

    **Matching Strategy:**
    1. If article_codes is provided in CSV, try to find and update that record
    2. If not found by article_codes OR article_codes not provided, match by promoter name
    3. When matching by promoter, if article_codes is also provided, prefer matching both
    4. If no exact match found, update the first record with matching promoter

    **CSV Format:**
    Headers (case-insensitive): products, article_codes (optional), promoter

    **Example CSV:**
    ```csv
    products,article_codes,promoter
    Updated Almonds Product Name,30027,Smart & Essentials Barcode
    Updated Cashew Product,30028,Smart & Essentials Barcode
    New Product Name,,Star Bazaar Barcode
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
            if col_lower in ['products', 'product', 'product_name', 'product name']:
                column_mapping[col] = 'products'
            elif col_lower in ['article_codes', 'article_code', 'article code', 'barcode']:
                column_mapping[col] = 'article_codes'
            elif col_lower in ['promoter', 'promoter name', 'promoter_name']:
                column_mapping[col] = 'promoter'

        # Rename columns
        df.rename(columns=column_mapping, inplace=True)

        # Check required column: promoter is minimum required
        if 'promoter' not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required column: promoter"
            )

        # Clean data
        if 'products' in df.columns:
            df['products'] = df['products'].fillna('').astype(str).str.strip()
        else:
            df['products'] = ''

        df['promoter'] = df['promoter'].fillna('').astype(str).str.strip()

        if 'article_codes' in df.columns:
            df['article_codes'] = pd.to_numeric(df['article_codes'], errors='coerce')
        else:
            df['article_codes'] = pd.NA

        # Process updates
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        not_found_count = 0
        matched_by_article_code = 0
        matched_by_promoter = 0
        errors = []

        for idx, row in df.iterrows():
            # Skip empty rows
            if row['promoter'] == '' and (pd.isna(row['article_codes']) or row['article_codes'] == ''):
                skipped_count += 1
                continue

            # Validate minimum required fields
            if not row['promoter']:
                errors.append({
                    "row": idx + 2,
                    "error": "Missing required field: promoter",
                    "data": row.to_dict()
                })
                failed_count += 1
                continue

            try:
                db_article = None
                match_type = None

                # Strategy 1: Try to match by article_codes if provided
                if not pd.isna(row['article_codes']):
                    article_code_value = int(row['article_codes'])
                    db_article = db.query(ArticleCode).filter(
                        ArticleCode.article_codes == article_code_value
                    ).first()

                    if db_article:
                        match_type = 'article_code'
                        matched_by_article_code += 1

                # Strategy 2: If not found by article_codes, try matching by promoter
                if not db_article:
                    # Strategy 2a: If article_codes provided, try matching both promoter AND article_codes
                    if not pd.isna(row['article_codes']):
                        article_code_value = int(row['article_codes'])
                        db_article = db.query(ArticleCode).filter(
                            ArticleCode.promoter == row['promoter'],
                            ArticleCode.article_codes == article_code_value
                        ).first()

                        if db_article:
                            match_type = 'promoter_with_article_code'
                            matched_by_promoter += 1

                    # Strategy 2b: If still not found, match by promoter only
                    if not db_article:
                        db_article = db.query(ArticleCode).filter(
                            ArticleCode.promoter == row['promoter']
                        ).first()

                        if db_article:
                            match_type = 'promoter_only'
                            matched_by_promoter += 1

                # Update if found
                if db_article:
                    # Update fields if provided in CSV
                    if row['products']:
                        db_article.products = row['products']
                    if not pd.isna(row['article_codes']):
                        # Only update article_codes if it doesn't conflict with existing unique values
                        new_article_code = int(row['article_codes'])
                        if db_article.article_codes != new_article_code:
                            # Check if new article code already exists elsewhere
                            existing = db.query(ArticleCode).filter(
                                ArticleCode.article_codes == new_article_code,
                                ArticleCode.id != db_article.id
                            ).first()

                            if existing:
                                errors.append({
                                    "row": idx + 2,
                                    "error": f"Cannot update article_codes to {new_article_code}: already exists in another record",
                                    "data": row.to_dict(),
                                    "match_type": match_type
                                })
                                failed_count += 1
                                continue

                            db_article.article_codes = new_article_code

                    # Promoter can always be updated
                    db_article.promoter = row['promoter']
                    updated_count += 1
                else:
                    # Not found
                    not_found_count += 1
                    errors.append({
                        "row": idx + 2,
                        "error": f"No matching record found for promoter '{row['promoter']}'" +
                                (f" and article_codes {int(row['article_codes'])}" if not pd.isna(row['article_codes']) else ""),
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
            matched_by_article_code=matched_by_article_code,
            matched_by_promoter=matched_by_promoter,
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
# PROMOTER CRUD ENDPOINTS
# ============================================================================

@router.get("/promoters", response_model=List[PromoterResponse])
def get_promoters(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    state: Optional[str] = Query(None, description="Filter by state"),
    point_of_sale: Optional[str] = Query(None, description="Filter by point of sale"),
    search: Optional[str] = Query(None, description="Search in state, POS, or promoter name")
):
    """
    Get all promoters with optional filtering.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **state**: Filter by specific state
    - **point_of_sale**: Filter by specific point of sale
    - **search**: Search in state, point of sale, or promoter name
    """
    query = db.query(Promoter)

    if state:
        query = query.filter(Promoter.state.ilike(f"%{state}%"))

    if point_of_sale:
        query = query.filter(Promoter.point_of_sale.ilike(f"%{point_of_sale}%"))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Promoter.state.ilike(search_pattern),
                Promoter.point_of_sale.ilike(search_pattern),
                Promoter.promoter.ilike(search_pattern)
            )
        )

    promoters = query.offset(skip).limit(limit).all()
    return promoters


@router.get("/promoters/{promoter_id}", response_model=PromoterResponse)
def get_promoter(
    promoter_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific promoter by ID.
    """
    promoter = db.query(Promoter).filter(Promoter.id == promoter_id).first()

    if not promoter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter with ID {promoter_id} not found"
        )

    return promoter


@router.post("/promoters", response_model=PromoterResponse, status_code=status.HTTP_201_CREATED)
def create_promoter(
    promoter: PromoterCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new promoter.

    - **state**: State name
    - **point_of_sale**: Point of sale name
    - **promoter**: Promoter name
    """
    # Create new promoter
    db_promoter = Promoter(**promoter.model_dump())
    db.add(db_promoter)
    db.commit()
    db.refresh(db_promoter)

    return db_promoter


@router.put("/promoters/{promoter_id}", response_model=PromoterResponse)
def update_promoter(
    promoter_id: int,
    promoter_update: PromoterUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing promoter.

    - **state**: State name (optional)
    - **point_of_sale**: Point of sale name (optional)
    - **promoter**: Promoter name (optional)
    """
    # Find the promoter
    db_promoter = db.query(Promoter).filter(Promoter.id == promoter_id).first()

    if not db_promoter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter with ID {promoter_id} not found"
        )

    # Update fields
    update_data = promoter_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_promoter, field, value)

    db.commit()
    db.refresh(db_promoter)

    return db_promoter


@router.delete("/promoters/{promoter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promoter(
    promoter_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a promoter by ID.
    """
    db_promoter = db.query(Promoter).filter(Promoter.id == promoter_id).first()

    if not db_promoter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter with ID {promoter_id} not found"
        )

    db.delete(db_promoter)
    db.commit()

    return None