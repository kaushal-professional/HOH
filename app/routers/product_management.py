"""
API Router for comprehensive Product Management.
Manages products with promoter assignments, pricing, and store assignments.

This router provides unified CRUD operations for:
- Products (products table)
- Promoter Assignments (article_codes table)
- Price Management (price_consolidated table)
- Store Assignments (store_products table)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.models.product import Store, StoreProduct
from app.models.article_code import Promoter
from app.services.product_management_repository import (
    ProductManagementRepository,
    PromoterAssignmentRepository,
    PriceManagementRepository,
)
from app.schemas.product_management import (
    ProductManagementCreate,
    ProductManagementUpdate,
    ProductManagementResponse,
    ProductManagementListResponse,
    PromoterAssignmentCreate,
    PromoterAssignmentResponse,
    PromoterAssignmentUpdateRequest,
    PriceCreate,
    PriceUpdate,
    PriceResponse,
    SuccessResponse,
    BulkOperationResponse,
    StoreAssignmentInfoResponse,
)

router = APIRouter(
    prefix="/product-management",
    tags=["Product Management (Unified)"]
)
security = HTTPBearer()


# ============================================================================
# Authentication Helper
# ============================================================================

def get_current_user_email(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
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
# PRODUCT MANAGEMENT ENDPOINTS (Unified CRUD)
# ============================================================================

@router.post(
    "/products",
    response_model=ProductManagementResponse,
    status_code=status.HTTP_201_CREATED
)
def create_product_with_assignments(
    product: ProductManagementCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Create a new product with all assignments.

    IMPORTANT - Request Body Format:
    - article_code: INTEGER (not string)
    - price: FLOAT (not string)
    - gst: FLOAT or null (not string)
    - store_ids: ARRAY of INTEGERS (not strings)
    - is_active: BOOLEAN (not string)

    This endpoint creates a product and optionally:
    - Assigns promoters (creates article codes)
    - Sets prices for different pricelists
    - Assigns to stores

    **Request Body:**
    ```json
    {
        "product_id": "Y0520",
        "product_type": "Almond",
        "product_description": "Almonds Non Pareil Running (25-29) Loose FG",
        "is_active": true,
        "promoter_assignments": [
            {
                "article_code": 902979,
                "promoter": "Smart & Essentials Barcode"
            }
        ],
        "prices": [
            {
                "pricelist": "Smart Bazaar",
                "price": 850.00,
                "gst": 0.05
            }
        ],
        "store_ids": [1, 2, 3]
    }
    ```
    """
    db_product = ProductManagementRepository.create_product_with_assignments(
        db, product
    )

    # Get full product data with all assignments
    product_data = ProductManagementRepository.get_product_with_all_data(
        db, db_product.product_id
    )

    return _format_product_response(product_data)


@router.get(
    "/products/{product_id}",
    response_model=ProductManagementResponse
)
def get_product_with_all_data(
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a product with all related data.

    Returns product with:
    - Promoter assignments
    - Prices across all pricelists
    - Store assignments
    """
    product_data = ProductManagementRepository.get_product_with_all_data(
        db, product_id
    )

    if not product_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    return _format_product_response(product_data)


@router.get(
    "/products",
    response_model=ProductManagementListResponse
)
def get_all_products_with_data(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Skip records"),
    limit: int = Query(20, ge=1, le=100, description="Limit records"),
    product_type: Optional[str] = Query(None, description="Filter by product type"),
    search: Optional[str] = Query(None, description="Search in product description"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    promoter: Optional[str] = Query(None, description="Filter by promoter name"),
    _: str = Depends(get_current_user_email)
):
    """
    Get all products with comprehensive data.

    Supports filtering by:
    - Product type
    - Search query
    - Active status
    - Promoter name

    Returns paginated results with all related data for each product.
    """
    products_data, total = ProductManagementRepository.get_all_products_with_data(
        db, skip, limit, product_type, search, is_active, promoter
    )

    products = [_format_product_response(pd) for pd in products_data]

    return ProductManagementListResponse(
        products=products,
        total=total,
        skip=skip,
        limit=limit
    )


@router.put(
    "/products/{product_id}",
    response_model=ProductManagementResponse
)
def update_product(
    product_id: str,
    update_data: ProductManagementUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Update product basic information.

    To update promoter assignments, prices, or store assignments,
    use the dedicated endpoints below.
    """
    updated_product = ProductManagementRepository.update_product(
        db, product_id, update_data
    )

    if not updated_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    # Get full product data
    product_data = ProductManagementRepository.get_product_with_all_data(
        db, product_id
    )

    return _format_product_response(product_data)


@router.delete(
    "/products/{product_id}",
    response_model=SuccessResponse
)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete a product and all related data.

    This will cascade delete:
    - Promoter assignments (article codes)
    - Prices
    - Store assignments
    """
    success = ProductManagementRepository.delete_product(db, product_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    return SuccessResponse(
        success=True,
        message=f"Product {product_id} and all related data deleted successfully"
    )


# ============================================================================
# PROMOTER ASSIGNMENT ENDPOINTS
# ============================================================================

@router.post(
    "/products/{product_id}/promoter-assignments",
    response_model=PromoterAssignmentResponse,
    status_code=status.HTTP_201_CREATED
)
def add_promoter_assignment(
    product_id: str,
    assignment: PromoterAssignmentCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Add a promoter assignment to a product.

    **Request Body:**
    ```json
    {
        "article_code": 902979,
        "promoter": "Smart & Essentials Barcode"
    }
    ```
    """
    # Get product
    product_data = ProductManagementRepository.get_product_with_all_data(
        db, product_id
    )
    if not product_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    product = product_data["product"]
    article_code = PromoterAssignmentRepository.add_promoter_assignment(
        db, product.product_description, assignment
    )

    return PromoterAssignmentResponse.model_validate(article_code)


@router.get(
    "/products/{product_id}/promoter-assignments",
    response_model=List[PromoterAssignmentResponse]
)
def get_promoter_assignments(
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get all promoter assignments for a product.
    """
    # Get product
    product_data = ProductManagementRepository.get_product_with_all_data(
        db, product_id
    )
    if not product_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    return [
        PromoterAssignmentResponse.model_validate(a)
        for a in product_data["promoter_assignments"]
    ]


@router.put(
    "/promoter-assignments/{assignment_id}",
    response_model=PromoterAssignmentResponse
)
def update_promoter_assignment(
    assignment_id: int,
    update_data: PromoterAssignmentUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Update a promoter assignment.

    **Request Body:**
    ```json
    {
        "promoter": "FP & Signature Barcode"
    }
    ```
    """
    if not update_data.promoter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promoter name is required"
        )

    updated = PromoterAssignmentRepository.update_promoter_assignment(
        db, assignment_id, update_data.promoter
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter assignment with ID {assignment_id} not found"
        )

    return PromoterAssignmentResponse.model_validate(updated)


@router.delete(
    "/promoter-assignments/{assignment_id}",
    response_model=SuccessResponse
)
def delete_promoter_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete a promoter assignment.
    """
    success = PromoterAssignmentRepository.delete_promoter_assignment(
        db, assignment_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter assignment with ID {assignment_id} not found"
        )

    return SuccessResponse(
        success=True,
        message=f"Promoter assignment {assignment_id} deleted successfully"
    )


# ============================================================================
# PRICE MANAGEMENT ENDPOINTS
# ============================================================================

@router.post(
    "/prices",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_price(
    price: PriceCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Create a price entry.

    **Request Body:**
    ```json
    {
        "pricelist": "Smart Bazaar",
        "product": "Almonds Non Pareil Running (25-29) Loose FG",
        "price": 850.00,
        "gst": 0.05
    }
    ```
    """
    db_price = PriceManagementRepository.create_price(db, price)
    return PriceResponse.model_validate(db_price)


@router.get(
    "/prices/{price_id}",
    response_model=PriceResponse
)
def get_price(
    price_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get a price entry by ID.
    """
    price = PriceManagementRepository.get_price_by_id(db, price_id)

    if not price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price with ID {price_id} not found"
        )

    return PriceResponse.model_validate(price)


@router.get(
    "/prices",
    response_model=dict
)
def get_all_prices(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    pricelist: Optional[str] = Query(None, description="Filter by pricelist"),
    product: Optional[str] = Query(None, description="Filter by product"),
    _: str = Depends(get_current_user_email)
):
    """
    Get all prices with optional filters.

    Supports filtering by pricelist and product name.
    """
    prices, total = PriceManagementRepository.get_all_prices(
        db, skip, limit, pricelist, product
    )

    return {
        "prices": [PriceResponse.model_validate(p) for p in prices],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get(
    "/products/{product_name}/prices",
    response_model=List[PriceResponse]
)
def get_prices_by_product(
    product_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get all prices for a specific product.
    """
    prices = PriceManagementRepository.get_prices_by_product(db, product_name)

    return [PriceResponse.model_validate(p) for p in prices]


@router.put(
    "/prices/{price_id}",
    response_model=PriceResponse
)
def update_price(
    price_id: int,
    update_data: PriceUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Update a price entry.

    **Request Body:**
    ```json
    {
        "price": 900.00,
        "gst": 0.12
    }
    ```
    """
    updated_price = PriceManagementRepository.update_price(
        db, price_id, update_data
    )

    if not updated_price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price with ID {price_id} not found"
        )

    return PriceResponse.model_validate(updated_price)


@router.delete(
    "/prices/{price_id}",
    response_model=SuccessResponse
)
def delete_price(
    price_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Delete a price entry.
    """
    success = PriceManagementRepository.delete_price(db, price_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price with ID {price_id} not found"
        )

    return SuccessResponse(
        success=True,
        message=f"Price {price_id} deleted successfully"
    )


# ============================================================================
# STORE-PROMOTER RELATIONSHIP ENDPOINTS
# ============================================================================

@router.get(
    "/stores/{store_id}/promoters",
    response_model=dict
)
def get_promoters_for_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get all promoters assigned to a specific store.

    This shows the Store -> Promoter relationship.
    Promoters are linked to stores via the promoter table's
    point_of_sale field matching the store name.
    """
    from app.models.product import Store
    from app.models.article_code import Promoter

    # Get store
    store = db.query(Store).filter(Store.store_id == store_id).first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with ID {store_id} not found"
        )

    # Find promoters for this store
    promoters = db.query(Promoter).filter(
        Promoter.point_of_sale.ilike(f"%{store.store_name}%")
    ).all()

    return {
        "store_id": store.store_id,
        "store_name": store.store_name,
        "state": store.state.state_name if store.state else None,
        "promoters": [
            {
                "id": p.id,
                "promoter": p.promoter,
                "point_of_sale": p.point_of_sale,
                "state": p.state
            }
            for p in promoters
        ],
        "total_promoters": len(promoters)
    }


@router.get(
    "/products/{product_id}/stores-with-promoters",
    response_model=dict
)
def get_product_stores_with_promoters(
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """
    Get all stores where a product is assigned, along with their promoters.

    This shows the complete relationship:
    Product -> Store -> Promoter
    """
    from app.models.product import StoreProduct
    from app.models.article_code import Promoter

    # Get product
    product_data = ProductManagementRepository.get_product_with_all_data(
        db, product_id
    )

    if not product_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    product = product_data["product"]

    # Get store assignments with promoters
    store_assignments = db.query(StoreProduct).options(
        joinedload(StoreProduct.store).joinedload(Store.state)
    ).filter(
        StoreProduct.product_id == product_id
    ).all()

    stores_with_promoters = []
    for sa in store_assignments:
        if sa.store:
            # Find promoters for this store
            promoters = db.query(Promoter).filter(
                Promoter.point_of_sale.ilike(f"%{sa.store.store_name}%")
            ).all()

            stores_with_promoters.append({
                "store_id": sa.store_id,
                "store_name": sa.store.store_name,
                "state": sa.store.state.state_name if sa.store.state else None,
                "is_available": sa.is_available,
                "promoters": [
                    {
                        "id": p.id,
                        "promoter": p.promoter,
                        "point_of_sale": p.point_of_sale
                    }
                    for p in promoters
                ]
            })

    return {
        "product_id": product.product_id,
        "product_description": product.product_description,
        "stores": stores_with_promoters,
        "total_stores": len(stores_with_promoters)
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_product_response(product_data: dict) -> ProductManagementResponse:
    """Format product data into response schema"""
    from app.models.article_code import Promoter
    from app.core.database import get_db

    product = product_data["product"]

    # Format promoter assignments
    promoter_assignments = [
        PromoterAssignmentResponse.model_validate(a)
        for a in product_data["promoter_assignments"]
    ]

    # Format prices
    prices = [
        PriceResponse.model_validate(p)
        for p in product_data["prices"]
    ]

    # Format store assignments with promoters
    store_assignments = []
    for sa in product_data["store_assignments"]:
        # Get promoters for this store
        # Use a simple session access - this is inside a request context
        from sqlalchemy.orm import Session
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            promoters_list = []
            if sa.store:
                # Find promoters via point_of_sale matching store_name
                promoters = db.query(Promoter).filter(
                    Promoter.point_of_sale.ilike(f"%{sa.store.store_name}%")
                ).all()
                promoters_list = [p.promoter for p in promoters]
        finally:
            db.close()

        store_assignments.append(
            StoreAssignmentInfoResponse(
                id=sa.id,
                store_id=sa.store_id,
                product_id=sa.product_id,
                store_name=sa.store.store_name if sa.store else "Unknown",
                state_name=sa.store.state.state_name if sa.store and sa.store.state else None,
                promoters=promoters_list,
                is_available=sa.is_available,
                created_at=sa.created_at,
                updated_at=sa.updated_at
            )
        )

    return ProductManagementResponse(
        product_id=product.product_id,
        product_type=product.product_type,
        product_description=product.product_description,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
        promoter_assignments=promoter_assignments,
        prices=prices,
        store_assignments=store_assignments
    )
