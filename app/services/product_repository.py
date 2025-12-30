"""
Repository layer for Product, State, Store, and Store-Product mapping operations.
Handles all database queries and operations for the store-product mapping system.
"""

from typing import List, Optional, Tuple
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.product import Product, State, Store, StoreProduct, StateProduct
from app.schemas.product import (
    ProductCreate, ProductUpdate,
    StateCreate, StateUpdate,
    StoreCreate, StoreUpdate,
    StoreProductCreate, StoreProductUpdate,
    StateProductCreate,
)


class ProductRepository:
    """Repository for Product operations"""

    @staticmethod
    def create(db: Session, product: ProductCreate) -> Product:
        """Create a new product"""
        # Check if product already exists
        existing = db.query(Product).filter(Product.product_id == product.product_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with ID {product.product_id} already exists"
            )

        db_product = Product(**product.model_dump())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product

    @staticmethod
    def get_by_id(db: Session, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        return db.query(Product).filter(Product.product_id == product_id).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        product_type: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Product], int]:
        """Get all products with optional filters"""
        query = db.query(Product)

        # Apply filters
        if product_type:
            query = query.filter(Product.product_type == product_type)
        if search:
            query = query.filter(Product.product_description.ilike(f"%{search}%"))
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)

        # Get total count
        total = query.count()

        # Get paginated results
        products = query.order_by(Product.product_type, Product.product_description)\
            .offset(skip).limit(limit).all()

        return products, total

    @staticmethod
    def update(db: Session, product_id: str, product_update: ProductUpdate) -> Optional[Product]:
        """Update product"""
        db_product = ProductRepository.get_by_id(db, product_id)
        if not db_product:
            return None

        update_data = product_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_product, field, value)

        db.commit()
        db.refresh(db_product)
        return db_product

    @staticmethod
    def delete(db: Session, product_id: str) -> bool:
        """Delete product (hard delete)"""
        db_product = ProductRepository.get_by_id(db, product_id)
        if not db_product:
            return False

        db.delete(db_product)
        db.commit()
        return True

    @staticmethod
    def get_product_types(db: Session) -> List[str]:
        """Get all unique product types"""
        types = db.query(Product.product_type).distinct().order_by(Product.product_type).all()
        return [t[0] for t in types]


class StateRepository:
    """Repository for State operations"""

    @staticmethod
    def create(db: Session, state: StateCreate) -> State:
        """Create a new state"""
        # Check if state already exists
        existing = db.query(State).filter(State.state_name == state.state_name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"State with name {state.state_name} already exists"
            )

        db_state = State(**state.model_dump())
        db.add(db_state)
        db.commit()
        db.refresh(db_state)
        return db_state

    @staticmethod
    def get_by_id(db: Session, state_id: int) -> Optional[State]:
        """Get state by ID"""
        return db.query(State).filter(State.state_id == state_id).first()

    @staticmethod
    def get_by_name(db: Session, state_name: str) -> Optional[State]:
        """Get state by name"""
        return db.query(State).filter(State.state_name == state_name).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> Tuple[List[State], int]:
        """Get all states"""
        query = db.query(State)

        if is_active is not None:
            query = query.filter(State.is_active == is_active)

        total = query.count()
        states = query.order_by(State.state_name).offset(skip).limit(limit).all()
        return states, total

    @staticmethod
    def update(db: Session, state_id: int, state_update: StateUpdate) -> Optional[State]:
        """Update state"""
        db_state = StateRepository.get_by_id(db, state_id)
        if not db_state:
            return None

        update_data = state_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_state, field, value)

        db.commit()
        db.refresh(db_state)
        return db_state

    @staticmethod
    def delete(db: Session, state_id: int) -> bool:
        """Delete state"""
        db_state = StateRepository.get_by_id(db, state_id)
        if not db_state:
            return False

        db.delete(db_state)
        db.commit()
        return True


class StoreRepository:
    """Repository for Store operations"""

    @staticmethod
    def create(db: Session, store: StoreCreate) -> Store:
        """Create a new store"""
        # Validate state exists
        state = StateRepository.get_by_id(db, store.state_id)
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"State with ID {store.state_id} not found"
            )

        db_store = Store(**store.model_dump())
        db.add(db_store)
        db.commit()
        db.refresh(db_store)
        return db_store

    @staticmethod
    def get_by_id(db: Session, store_id: int) -> Optional[Store]:
        """Get store by ID with state info"""
        return db.query(Store).options(joinedload(Store.state)).filter(Store.store_id == store_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Store]:
        """Get store by email"""
        return db.query(Store).options(joinedload(Store.state)).filter(Store.email == email).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        state_id: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Store], int]:
        """Get all stores"""
        query = db.query(Store).options(joinedload(Store.state))

        if state_id:
            query = query.filter(Store.state_id == state_id)
        if is_active is not None:
            query = query.filter(Store.is_active == is_active)

        total = query.count()
        stores = query.order_by(Store.store_name).offset(skip).limit(limit).all()
        return stores, total

    @staticmethod
    def update(db: Session, store_id: int, store_update: StoreUpdate) -> Optional[Store]:
        """Update store"""
        db_store = StoreRepository.get_by_id(db, store_id)
        if not db_store:
            return None

        # Validate new state_id if provided
        if store_update.state_id is not None:
            state = StateRepository.get_by_id(db, store_update.state_id)
            if not state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"State with ID {store_update.state_id} not found"
                )

        update_data = store_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_store, field, value)

        db.commit()
        db.refresh(db_store)
        return db_store

    @staticmethod
    def delete(db: Session, store_id: int) -> bool:
        """Delete store"""
        db_store = StoreRepository.get_by_id(db, store_id)
        if not db_store:
            return False

        db.delete(db_store)
        db.commit()
        return True

    @staticmethod
    def get_store_with_product_count(db: Session, store_id: int) -> Optional[dict]:
        """Get store with total product count"""
        store = StoreRepository.get_by_id(db, store_id)
        if not store:
            return None

        product_count = db.query(StoreProduct).filter(
            StoreProduct.store_id == store_id,
            StoreProduct.is_available == True
        ).count()

        return {
            "store": store,
            "total_products": product_count
        }


class StoreProductRepository:
    """Repository for Store-Product mapping operations"""

    @staticmethod
    def create(db: Session, mapping: StoreProductCreate) -> StoreProduct:
        """Create a new store-product mapping"""
        # Validate store and product exist
        store = StoreRepository.get_by_id(db, mapping.store_id)
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Store with ID {mapping.store_id} not found"
            )

        product = ProductRepository.get_by_id(db, mapping.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {mapping.product_id} not found"
            )

        # Check if mapping already exists
        existing = db.query(StoreProduct).filter(
            and_(
                StoreProduct.store_id == mapping.store_id,
                StoreProduct.product_id == mapping.product_id
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mapping already exists for store {mapping.store_id} and product {mapping.product_id}"
            )

        db_mapping = StoreProduct(**mapping.model_dump())
        db.add(db_mapping)
        db.commit()
        db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    def bulk_create(db: Session, store_id: int, product_ids: List[str], is_available: bool = True) -> dict:
        """Bulk create store-product mappings"""
        # Validate store exists
        store = StoreRepository.get_by_id(db, store_id)
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Store with ID {store_id} not found"
            )

        created_count = 0
        failed_count = 0
        errors = []

        for product_id in product_ids:
            try:
                # Check if product exists
                product = ProductRepository.get_by_id(db, product_id)
                if not product:
                    errors.append(f"Product {product_id} not found")
                    failed_count += 1
                    continue

                # Check if mapping already exists
                existing = db.query(StoreProduct).filter(
                    and_(
                        StoreProduct.store_id == store_id,
                        StoreProduct.product_id == product_id
                    )
                ).first()

                if existing:
                    errors.append(f"Mapping already exists for product {product_id}")
                    failed_count += 1
                    continue

                # Create mapping
                db_mapping = StoreProduct(
                    store_id=store_id,
                    product_id=product_id,
                    is_available=is_available
                )
                db.add(db_mapping)
                created_count += 1

            except Exception as e:
                errors.append(f"Failed to add product {product_id}: {str(e)}")
                failed_count += 1

        db.commit()

        return {
            "success": True,
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors
        }

    @staticmethod
    def get_by_id(db: Session, mapping_id: int) -> Optional[StoreProduct]:
        """Get store-product mapping by ID"""
        return db.query(StoreProduct).options(
            joinedload(StoreProduct.product)
        ).filter(StoreProduct.id == mapping_id).first()

    @staticmethod
    def get_by_store_and_product(db: Session, store_id: int, product_id: str) -> Optional[StoreProduct]:
        """Get mapping by store and product"""
        return db.query(StoreProduct).filter(
            and_(
                StoreProduct.store_id == store_id,
                StoreProduct.product_id == product_id
            )
        ).first()

    @staticmethod
    def get_products_by_store(
        db: Session,
        store_id: int,
        skip: int = 0,
        limit: int = 100,
        is_available: Optional[bool] = None
    ) -> Tuple[List[StoreProduct], int]:
        """Get all products for a store"""
        query = db.query(StoreProduct).options(
            joinedload(StoreProduct.product)
        ).filter(StoreProduct.store_id == store_id)

        if is_available is not None:
            query = query.filter(StoreProduct.is_available == is_available)

        total = query.count()
        mappings = query.offset(skip).limit(limit).all()
        return mappings, total

    @staticmethod
    def update(db: Session, mapping_id: int, update: StoreProductUpdate) -> Optional[StoreProduct]:
        """Update store-product mapping"""
        db_mapping = StoreProductRepository.get_by_id(db, mapping_id)
        if not db_mapping:
            return None

        update_data = update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_mapping, field, value)

        db.commit()
        db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    def delete(db: Session, mapping_id: int) -> bool:
        """Delete store-product mapping"""
        db_mapping = StoreProductRepository.get_by_id(db, mapping_id)
        if not db_mapping:
            return False

        db.delete(db_mapping)
        db.commit()
        return True

    @staticmethod
    def delete_by_store_and_product(db: Session, store_id: int, product_id: str) -> bool:
        """Delete mapping by store and product"""
        db_mapping = StoreProductRepository.get_by_store_and_product(db, store_id, product_id)
        if not db_mapping:
            return False

        db.delete(db_mapping)
        db.commit()
        return True


class UserProductRepository:
    """Repository for user-specific product queries"""

    @staticmethod
    def get_products_by_user_email(
        db: Session,
        user_email: str,
        skip: int = 0,
        limit: int = 100,
        product_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Product], int]:
        """Get all products available for a user based on their store email"""
        query = db.query(Product).join(
            StoreProduct, Product.product_id == StoreProduct.product_id
        ).join(
            Store, StoreProduct.store_id == Store.store_id
        ).filter(
            Store.email == user_email,
            StoreProduct.is_available == True,
            Product.is_active == True,
            Store.is_active == True
        )

        # Apply filters
        if product_type:
            query = query.filter(Product.product_type == product_type)
        if search:
            query = query.filter(Product.product_description.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Get paginated results
        products = query.order_by(Product.product_type, Product.product_description)\
            .offset(skip).limit(limit).all()

        return products, total

    @staticmethod
    def check_product_availability(db: Session, user_email: str, product_id: str) -> bool:
        """Check if a specific product is available for a user's store"""
        count = db.query(StoreProduct).join(
            Store, StoreProduct.store_id == Store.store_id
        ).filter(
            Store.email == user_email,
            StoreProduct.product_id == product_id,
            StoreProduct.is_available == True,
            Store.is_active == True
        ).count()

        return count > 0

    @staticmethod
    def get_store_info_by_email(db: Session, user_email: str) -> Optional[dict]:
        """Get store information for a user"""
        store = db.query(Store).options(
            joinedload(Store.state)
        ).filter(Store.email == user_email, Store.is_active == True).first()

        if not store:
            return None

        # Get product count
        product_count = db.query(StoreProduct).filter(
            StoreProduct.store_id == store.store_id,
            StoreProduct.is_available == True
        ).count()

        return {
            "store": store,
            "total_products": product_count
        }

    @staticmethod
    def get_product_types_by_user(db: Session, user_email: str) -> List[str]:
        """Get all product types available for a user's store"""
        types = db.query(Product.product_type).join(
            StoreProduct, Product.product_id == StoreProduct.product_id
        ).join(
            Store, StoreProduct.store_id == Store.store_id
        ).filter(
            Store.email == user_email,
            StoreProduct.is_available == True,
            Product.is_active == True,
            Store.is_active == True
        ).distinct().order_by(Product.product_type).all()

        return [t[0] for t in types]


class StateProductRepository:
    """Repository for State-Product mapping operations"""

    @staticmethod
    def create(db: Session, mapping: StateProductCreate) -> StateProduct:
        """Create a new state-product mapping"""
        # Validate state and product exist
        state = StateRepository.get_by_id(db, mapping.state_id)
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"State with ID {mapping.state_id} not found"
            )

        product = ProductRepository.get_by_id(db, mapping.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {mapping.product_id} not found"
            )

        # Check if mapping already exists
        existing = db.query(StateProduct).filter(
            and_(
                StateProduct.state_id == mapping.state_id,
                StateProduct.product_id == mapping.product_id
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mapping already exists for state {mapping.state_id} and product {mapping.product_id}"
            )

        db_mapping = StateProduct(**mapping.model_dump())
        db.add(db_mapping)
        db.commit()
        db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    def bulk_create(db: Session, state_id: int, product_ids: List[str]) -> dict:
        """Bulk create state-product mappings"""
        # Validate state exists
        state = StateRepository.get_by_id(db, state_id)
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"State with ID {state_id} not found"
            )

        created_count = 0
        failed_count = 0
        errors = []

        for product_id in product_ids:
            try:
                # Check if product exists
                product = ProductRepository.get_by_id(db, product_id)
                if not product:
                    errors.append(f"Product {product_id} not found")
                    failed_count += 1
                    continue

                # Check if mapping already exists
                existing = db.query(StateProduct).filter(
                    and_(
                        StateProduct.state_id == state_id,
                        StateProduct.product_id == product_id
                    )
                ).first()

                if existing:
                    errors.append(f"Mapping already exists for product {product_id}")
                    failed_count += 1
                    continue

                # Create mapping
                db_mapping = StateProduct(
                    state_id=state_id,
                    product_id=product_id
                )
                db.add(db_mapping)
                created_count += 1

            except Exception as e:
                errors.append(f"Failed to add product {product_id}: {str(e)}")
                failed_count += 1

        db.commit()

        return {
            "success": True,
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors
        }

    @staticmethod
    def delete(db: Session, state_id: int, product_id: str) -> bool:
        """Delete state-product mapping"""
        db_mapping = db.query(StateProduct).filter(
            and_(
                StateProduct.state_id == state_id,
                StateProduct.product_id == product_id
            )
        ).first()

        if not db_mapping:
            return False

        db.delete(db_mapping)
        db.commit()
        return True
