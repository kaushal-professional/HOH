"""
API Router for Product, State, Store, and Store-Product mapping endpoints.
Full CRUD operations for the store-product availability system.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import decode_access_token
from app.services.product_repository import (
    ProductRepository,
    StateRepository,
    StoreRepository,
    StoreProductRepository,
    StateProductRepository,
    UserProductRepository,
)
from app.schemas.product import (
    # Product schemas
    ProductCreate, ProductUpdate, ProductResponse,
    # State schemas
    StateCreate, StateUpdate, StateResponse,
    # Store schemas
    StoreCreate, StoreUpdate, StoreResponse, StoreDetailResponse,
    # Store-Product mapping schemas
    StoreProductCreate, StoreProductBulkCreate, StoreProductUpdate,
    StoreProductResponse, StoreProductDetailResponse,
    # State-Product mapping schemas
    StateProductCreate, StateProductBulkCreate, StateProductResponse,
    # User query schemas
    ProductAvailabilityCheck, UserProductsResponse, ProductTypeResponse,
    # Utility schemas
    SuccessResponse, ErrorResponse, BulkOperationResponse,
)

router = APIRouter(prefix="/products", tags=["Products & Store Mapping"])
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
# USER-FACING ENDPOINTS (For logged-in users to see their products)
# ============================================================================

@router.get("/my-products", response_model=UserProductsResponse)
def get_my_products(
    user_email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    product_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """
    Get all products available for the authenticated user's store.

    This is the main endpoint users will call to see their available products.
    """
    # Get store info
    store_info = UserProductRepository.get_store_info_by_email(db, user_email)
    if not store_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found for this user"
        )

    # Get products
    products, total = UserProductRepository.get_products_by_user_email(
        db, user_email, skip, limit, product_type, search
    )

    return UserProductsResponse(
        store_info=StoreDetailResponse(
            **{**store_info["store"].__dict__, "total_products": store_info["total_products"]}
        ),
        products=[ProductResponse.model_validate(p) for p in products],
        total_count=total
    )


@router.get("/my-products/check/{product_id}", response_model=ProductAvailabilityCheck)
def check_my_product_availability(
    product_id: str,
    user_email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """Check if a specific product is available for the authenticated user's store"""
    is_available = UserProductRepository.check_product_availability(db, user_email, product_id)

    return ProductAvailabilityCheck(
        product_id=product_id,
        is_available=is_available
    )


@router.get("/my-products/types", response_model=ProductTypeResponse)
def get_my_product_types(
    user_email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """Get all product types available for the authenticated user's store"""
    types = UserProductRepository.get_product_types_by_user(db, user_email)

    return ProductTypeResponse(
        product_types=types,
        count=len(types)
    )


@router.get("/my-store", response_model=StoreDetailResponse)
def get_my_store_info(
    user_email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """Get store information for the authenticated user"""
    store_info = UserProductRepository.get_store_info_by_email(db, user_email)
    if not store_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found for this user"
        )

    return StoreDetailResponse(
        **{**store_info["store"].__dict__, "total_products": store_info["total_products"]}
    )


# ============================================================================
# PRODUCT CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)  # Require authentication
):
    """Create a new product"""
    db_product = ProductRepository.create(db, product)
    return ProductResponse.model_validate(db_product)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Get product by ID"""
    product = ProductRepository.get_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    return ProductResponse.model_validate(product)


@router.get("/", response_model=dict)
def get_all_products(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    product_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    _: str = Depends(get_current_user_email)
):
    """Get all products with optional filters"""
    products, total = ProductRepository.get_all(
        db, skip, limit, product_type, search, is_active
    )

    return {
        "products": [ProductResponse.model_validate(p) for p in products],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Update product"""
    updated_product = ProductRepository.update(db, product_id, product_update)
    if not updated_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    return ProductResponse.model_validate(updated_product)


@router.delete("/{product_id}", response_model=SuccessResponse)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Delete product"""
    success = ProductRepository.delete(db, product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"Product {product_id} deleted successfully"
    )


@router.get("/types/list", response_model=ProductTypeResponse)
def get_product_types(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Get all unique product types"""
    types = ProductRepository.get_product_types(db)
    return ProductTypeResponse(
        product_types=types,
        count=len(types)
    )


# ============================================================================
# STATE CRUD ENDPOINTS
# ============================================================================

@router.post("/states/", response_model=StateResponse, status_code=status.HTTP_201_CREATED)
def create_state(
    state: StateCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Create a new state"""
    db_state = StateRepository.create(db, state)
    return StateResponse.model_validate(db_state)


@router.get("/states/{state_id}", response_model=StateResponse)
def get_state(
    state_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Get state by ID"""
    state = StateRepository.get_by_id(db, state_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {state_id} not found"
        )
    return StateResponse.model_validate(state)


@router.get("/states/", response_model=dict)
def get_all_states(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    _: str = Depends(get_current_user_email)
):
    """Get all states"""
    states, total = StateRepository.get_all(db, skip, limit, is_active)

    return {
        "states": [StateResponse.model_validate(s) for s in states],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/states/{state_id}", response_model=StateResponse)
def update_state(
    state_id: int,
    state_update: StateUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Update state"""
    updated_state = StateRepository.update(db, state_id, state_update)
    if not updated_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {state_id} not found"
        )
    return StateResponse.model_validate(updated_state)


@router.delete("/states/{state_id}", response_model=SuccessResponse)
def delete_state(
    state_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Delete state"""
    success = StateRepository.delete(db, state_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {state_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"State {state_id} deleted successfully"
    )


# ============================================================================
# STORE CRUD ENDPOINTS
# ============================================================================

@router.post("/stores/", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
def create_store(
    store: StoreCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Create a new store"""
    db_store = StoreRepository.create(db, store)
    return StoreResponse.model_validate(db_store)


@router.get("/stores/{store_id}", response_model=StoreDetailResponse)
def get_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Get store by ID with product count"""
    store_info = StoreRepository.get_store_with_product_count(db, store_id)
    if not store_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with ID {store_id} not found"
        )
    return StoreDetailResponse(
        **{**store_info["store"].__dict__, "total_products": store_info["total_products"]}
    )


@router.get("/stores/", response_model=dict)
def get_all_stores(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    state_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    _: str = Depends(get_current_user_email)
):
    """Get all stores"""
    stores, total = StoreRepository.get_all(db, skip, limit, state_id, is_active)

    return {
        "stores": [StoreResponse.model_validate(s) for s in stores],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/stores/{store_id}", response_model=StoreResponse)
def update_store(
    store_id: int,
    store_update: StoreUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Update store"""
    updated_store = StoreRepository.update(db, store_id, store_update)
    if not updated_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with ID {store_id} not found"
        )
    return StoreResponse.model_validate(updated_store)


@router.delete("/stores/{store_id}", response_model=SuccessResponse)
def delete_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Delete store"""
    success = StoreRepository.delete(db, store_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with ID {store_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"Store {store_id} deleted successfully"
    )


# ============================================================================
# STORE-PRODUCT MAPPING ENDPOINTS
# ============================================================================

@router.post("/mappings/", response_model=StoreProductResponse, status_code=status.HTTP_201_CREATED)
def create_store_product_mapping(
    mapping: StoreProductCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Create a new store-product mapping"""
    db_mapping = StoreProductRepository.create(db, mapping)
    return StoreProductResponse.model_validate(db_mapping)


@router.post("/mappings/bulk", response_model=BulkOperationResponse)
def bulk_create_store_product_mappings(
    bulk_create: StoreProductBulkCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Bulk create store-product mappings"""
    result = StoreProductRepository.bulk_create(
        db, bulk_create.store_id, bulk_create.product_ids, bulk_create.is_available
    )
    return BulkOperationResponse(**result)


@router.get("/mappings/{mapping_id}", response_model=StoreProductDetailResponse)
def get_store_product_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Get store-product mapping by ID"""
    mapping = StoreProductRepository.get_by_id(db, mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping with ID {mapping_id} not found"
        )
    return StoreProductDetailResponse.model_validate(mapping)


@router.get("/mappings/store/{store_id}", response_model=dict)
def get_store_products(
    store_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_available: Optional[bool] = Query(None),
    _: str = Depends(get_current_user_email)
):
    """Get all products for a specific store"""
    mappings, total = StoreProductRepository.get_products_by_store(
        db, store_id, skip, limit, is_available
    )

    return {
        "mappings": [StoreProductDetailResponse.model_validate(m) for m in mappings],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/mappings/{mapping_id}", response_model=StoreProductResponse)
def update_store_product_mapping(
    mapping_id: int,
    update: StoreProductUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Update store-product mapping (mainly for is_available)"""
    updated_mapping = StoreProductRepository.update(db, mapping_id, update)
    if not updated_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping with ID {mapping_id} not found"
        )
    return StoreProductResponse.model_validate(updated_mapping)


@router.delete("/mappings/{mapping_id}", response_model=SuccessResponse)
def delete_store_product_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Delete store-product mapping"""
    success = StoreProductRepository.delete(db, mapping_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping with ID {mapping_id} not found"
        )
    return SuccessResponse(
        success=True,
        message=f"Mapping {mapping_id} deleted successfully"
    )


@router.delete("/mappings/store/{store_id}/product/{product_id}", response_model=SuccessResponse)
def delete_store_product_by_ids(
    store_id: int,
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Delete store-product mapping by store ID and product ID"""
    success = StoreProductRepository.delete_by_store_and_product(db, store_id, product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping not found for store {store_id} and product {product_id}"
        )
    return SuccessResponse(
        success=True,
        message=f"Mapping deleted for store {store_id} and product {product_id}"
    )


# ============================================================================
# STATE-PRODUCT MAPPING ENDPOINTS (Optional)
# ============================================================================

@router.post("/state-mappings/", response_model=StateProductResponse, status_code=status.HTTP_201_CREATED)
def create_state_product_mapping(
    mapping: StateProductCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Create a new state-product mapping"""
    db_mapping = StateProductRepository.create(db, mapping)
    return StateProductResponse.model_validate(db_mapping)


@router.post("/state-mappings/bulk", response_model=BulkOperationResponse)
def bulk_create_state_product_mappings(
    bulk_create: StateProductBulkCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Bulk create state-product mappings"""
    result = StateProductRepository.bulk_create(
        db, bulk_create.state_id, bulk_create.product_ids
    )
    return BulkOperationResponse(**result)


@router.delete("/state-mappings/state/{state_id}/product/{product_id}", response_model=SuccessResponse)
def delete_state_product_mapping(
    state_id: int,
    product_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email)
):
    """Delete state-product mapping"""
    success = StateProductRepository.delete(db, state_id, product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping not found for state {state_id} and product {product_id}"
        )
    return SuccessResponse(
        success=True,
        message=f"State-product mapping deleted for state {state_id} and product {product_id}"
    )
