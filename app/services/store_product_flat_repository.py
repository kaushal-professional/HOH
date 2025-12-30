"""
Repository for Store Product Flat table operations.
Handles all database operations for the store_product (singular) table.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.store_product_flat import StoreProductFlat
from app.schemas.store_product_flat import (
    StoreProductFlatCreate,
    StoreProductFlatUpdate,
    StoreProductFlatFilter,
)


class StoreProductFlatRepository:
    """Repository for Store Product Flat table operations"""

    @staticmethod
    def create(db: Session, entry: StoreProductFlatCreate) -> StoreProductFlat:
        """Create a new store product entry"""
        db_entry = StoreProductFlat(
            ykey=entry.ykey,
            product_name=entry.product_name,
            store=entry.store,
            state=entry.state
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def bulk_create(db: Session, entries: List[StoreProductFlatCreate]) -> dict:
        """Bulk create store product entries"""
        created_count = 0
        failed_count = 0
        errors = []

        for entry in entries:
            try:
                db_entry = StoreProductFlat(
                    ykey=entry.ykey,
                    product_name=entry.product_name,
                    store=entry.store,
                    state=entry.state
                )
                db.add(db_entry)
                created_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to create entry for {entry.ykey} at {entry.store}: {str(e)}")

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "created_count": 0,
                "failed_count": len(entries),
                "errors": [f"Bulk commit failed: {str(e)}"]
            }

        return {
            "success": True,
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors
        }

    @staticmethod
    def get_by_id(db: Session, entry_id: int) -> Optional[StoreProductFlat]:
        """Get store product entry by ID"""
        return db.query(StoreProductFlat).filter(StoreProductFlat.id == entry_id).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[StoreProductFlatFilter] = None
    ) -> Tuple[List[StoreProductFlat], int]:
        """
        Get all store product entries with optional filters and pagination.
        Returns: (list of entries, total count)
        """
        query = db.query(StoreProductFlat)

        # Apply filters
        if filters:
            if filters.ykey:
                query = query.filter(StoreProductFlat.ykey == filters.ykey)
            if filters.store:
                query = query.filter(StoreProductFlat.store.ilike(f"%{filters.store}%"))
            if filters.state:
                query = query.filter(StoreProductFlat.state.ilike(filters.state))
            if filters.search:
                query = query.filter(StoreProductFlat.product_name.ilike(f"%{filters.search}%"))

        # Get total count
        total = query.count()

        # Apply pagination
        entries = query.order_by(StoreProductFlat.id.desc()).offset(skip).limit(limit).all()

        return entries, total

    @staticmethod
    def update(
        db: Session,
        entry_id: int,
        entry_update: StoreProductFlatUpdate
    ) -> Optional[StoreProductFlat]:
        """Update a store product entry"""
        db_entry = db.query(StoreProductFlat).filter(StoreProductFlat.id == entry_id).first()

        if not db_entry:
            return None

        # Update fields if provided
        update_data = entry_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_entry, field, value)

        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def delete(db: Session, entry_id: int) -> bool:
        """Delete a store product entry"""
        db_entry = db.query(StoreProductFlat).filter(StoreProductFlat.id == entry_id).first()

        if not db_entry:
            return False

        db.delete(db_entry)
        db.commit()
        return True

    @staticmethod
    def delete_by_ykey_and_store(db: Session, ykey: str, store: str) -> bool:
        """Delete store product entries by YKEY and store"""
        result = db.query(StoreProductFlat).filter(
            StoreProductFlat.ykey == ykey,
            StoreProductFlat.store == store
        ).delete()

        db.commit()
        return result > 0

    # ============================================================================
    # Query Methods
    # ============================================================================

    @staticmethod
    def get_by_ykey(db: Session, ykey: str, skip: int = 0, limit: int = 100) -> Tuple[List[StoreProductFlat], int]:
        """Get all entries for a specific YKEY"""
        query = db.query(StoreProductFlat).filter(StoreProductFlat.ykey == ykey)
        total = query.count()
        entries = query.offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_store(db: Session, store: str, skip: int = 0, limit: int = 100) -> Tuple[List[StoreProductFlat], int]:
        """Get all entries for a specific store"""
        query = db.query(StoreProductFlat).filter(StoreProductFlat.store.ilike(f"%{store}%"))
        total = query.count()
        entries = query.offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_state(db: Session, state: str, skip: int = 0, limit: int = 100) -> Tuple[List[StoreProductFlat], int]:
        """Get all entries for a specific state"""
        query = db.query(StoreProductFlat).filter(StoreProductFlat.state.ilike(state))
        total = query.count()
        entries = query.offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_store_and_state(db: Session, store: str, state: str) -> Tuple[List[StoreProductFlat], int]:
        """Get all entries for a specific store and state combination"""
        query = db.query(StoreProductFlat).filter(
            StoreProductFlat.store.ilike(store),
            StoreProductFlat.state.ilike(state)
        )
        total = query.count()
        entries = query.all()
        return entries, total

    # ============================================================================
    # Statistics Methods
    # ============================================================================

    @staticmethod
    def get_statistics(db: Session) -> dict:
        """Get overall statistics"""
        total_entries = db.query(func.count(StoreProductFlat.id)).scalar()
        unique_ykeys = db.query(func.count(func.distinct(StoreProductFlat.ykey))).scalar()
        unique_stores = db.query(func.count(func.distinct(StoreProductFlat.store))).scalar()
        unique_states = db.query(func.count(func.distinct(StoreProductFlat.state))).scalar()

        return {
            "total_entries": total_entries,
            "unique_ykeys": unique_ykeys,
            "unique_stores": unique_stores,
            "unique_states": unique_states
        }

    @staticmethod
    def group_by_state(db: Session) -> List[dict]:
        """Group entries by state"""
        results = db.query(
            StoreProductFlat.state,
            func.count(StoreProductFlat.id).label('count')
        ).group_by(StoreProductFlat.state).order_by(func.count(StoreProductFlat.id).desc()).all()

        return [{"state": r.state, "count": r.count} for r in results]

    @staticmethod
    def group_by_store(db: Session) -> List[dict]:
        """Group entries by store"""
        results = db.query(
            StoreProductFlat.store,
            StoreProductFlat.state,
            func.count(StoreProductFlat.id).label('count')
        ).group_by(
            StoreProductFlat.store,
            StoreProductFlat.state
        ).order_by(func.count(StoreProductFlat.id).desc()).all()

        return [{"store": r.store, "state": r.state, "count": r.count} for r in results]

    @staticmethod
    def group_by_ykey(db: Session) -> List[dict]:
        """Group entries by YKEY"""
        results = db.query(
            StoreProductFlat.ykey,
            StoreProductFlat.product_name,
            func.count(StoreProductFlat.id).label('count')
        ).group_by(
            StoreProductFlat.ykey,
            StoreProductFlat.product_name
        ).order_by(func.count(StoreProductFlat.id).desc()).all()

        return [{"ykey": r.ykey, "product_name": r.product_name, "count": r.count} for r in results]

    @staticmethod
    def get_unique_ykeys(db: Session) -> List[str]:
        """Get list of unique YKEYs"""
        results = db.query(func.distinct(StoreProductFlat.ykey)).order_by(StoreProductFlat.ykey).all()
        return [r[0] for r in results]

    @staticmethod
    def get_unique_stores(db: Session) -> List[str]:
        """Get list of unique stores"""
        results = db.query(func.distinct(StoreProductFlat.store)).order_by(StoreProductFlat.store).all()
        return [r[0] for r in results]

    @staticmethod
    def get_unique_states(db: Session) -> List[str]:
        """Get list of unique states"""
        results = db.query(func.distinct(StoreProductFlat.state)).order_by(StoreProductFlat.state).all()
        return [r[0] for r in results]
