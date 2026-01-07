"""
API Router for Article Code and Promoter endpoints.
Includes barcode scanning and full CRUD operations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_
import numpy as np
import cv2
from PIL import Image
import zxingcpp

from app.core.database import get_db
from app.models.article_code import ArticleCode, Promoter
from app.models.price_consolidated import PriceConsolidated
from app.schemas.article_code import (
    ArticleCodeCreate, ArticleCodeUpdate, ArticleCodeResponse,
    PromoterCreate, PromoterUpdate, PromoterResponse,
    BarcodeScanRequest, BarcodeScanResponse, ArticleLookupRequest
)
from app.services.barcode_decoder import BarcodeDecoder
from app.services.excel_data_loader import excel_loader

router = APIRouter(prefix="/article-codes", tags=["Article Codes & Promoters"])


# ============================================================================
# HELPER FUNCTIONS FOR IMAGE PROCESSING
# ============================================================================

def preprocess_with_cv2(bgr: np.ndarray) -> np.ndarray:
    """
    Returns a processed grayscale image (uint8) ready for barcode decoding.
    
    Args:
        bgr: BGR image array from OpenCV
        
    Returns:
        Processed grayscale image optimized for barcode scanning
    """
    # 1) Grayscale
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 2) Upscale for better detection
    h, w = gray.shape[:2]
    scale = 2.0 if max(h, w) < 1200 else 1.5
    if scale != 1.0:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # 3) Apply bilateral filter to reduce noise while preserving edges
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # 4) Local contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 5) Adaptive thresholding to create binary image (helps with barcode detection)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)

    # 6) Morphological operations to clean up the image
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return binary


# ============================================================================
# BARCODE SCAN ENDPOINT
# ============================================================================

@router.post("/barcode-scan", response_model=BarcodeScanResponse, status_code=status.HTTP_200_OK)
async def scan_barcode(
    file: UploadFile = File(..., description="Image file containing barcode"),
    store_name: str = Form(..., description="Store name where scan occurred"),
    preprocess: bool = Form(True, description="Apply image preprocessing for better detection"),
    db: Session = Depends(get_db)
):
    """
    Scan barcode from uploaded image and retrieve product information including price with GST and weight.

    This endpoint:
    1. Accepts an image file containing a barcode
    2. Extracts the barcode text using zxing-cpp with optional preprocessing
    3. Decodes the barcode to extract article code and weight
    4. Retrieves product and price information from the database

    - **file**: Image file (JPEG, PNG, etc.) containing the barcode
    - **store_name**: The store name where the scan occurred (e.g., "Food Square", "Reliance Smart")
    - **preprocess**: Whether to apply image preprocessing (default: true)

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
    # Step 1: Extract barcode text from image
    try:
        image_data = await file.read()
        
        # Decode image bytes to OpenCV BGR
        np_buf = np.frombuffer(image_data, dtype=np.uint8)
        bgr = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
        
        if bgr is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file. Could not decode image."
            )

        # Preprocess or use original image
        if preprocess:
            gray = preprocess_with_cv2(bgr)
            img_for_zxing = Image.fromarray(gray)  # mode "L"
        else:
            # Pass original image (convert BGR -> RGB for PIL)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img_for_zxing = Image.fromarray(rgb)

        # Extract barcode(s) from image
        results = zxingcpp.read_barcodes(img_for_zxing)
        
        # If no results with preprocessing, try without it (fallback)
        if not results or len(results) == 0:
            if preprocess:
                # Try with original image as fallback
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                img_for_zxing = Image.fromarray(rgb)
                results = zxingcpp.read_barcodes(img_for_zxing)
            
            # If still no results, try with simple grayscale
            if not results or len(results) == 0:
                gray_simple = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                img_for_zxing = Image.fromarray(gray_simple)
                results = zxingcpp.read_barcodes(img_for_zxing)
        
        if not results or len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No barcode detected in the image. Please ensure the image contains a clear barcode."
            )
        
        # Use the first detected barcode
        barcode_text = results[0].text
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing image: {str(e)}"
        )
    
    # Step 2: Decode the barcode to extract article code and weight
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

@router.get("/article-codes", response_model=List[ArticleCodeResponse])
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


@router.get("/article-codes/{article_code_id}", response_model=ArticleCodeResponse)
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


@router.post("/article-codes", response_model=ArticleCodeResponse, status_code=status.HTTP_201_CREATED)
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


@router.put("/article-codes/{article_code_id}", response_model=ArticleCodeResponse)
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


@router.delete("/article-codes/{article_code_id}", status_code=status.HTTP_204_NO_CONTENT)
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
