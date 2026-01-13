"""
Repository layer for Price Consolidated operations.
Handles all database queries and operations for the price_consolidated table.
"""

from typing import List, Optional, Tuple
from decimal import Decimal
from sqlalchemy import or_, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.price_consolidated import PriceConsolidated
from app.schemas.price_consolidated import PriceConsolidatedCreate, PriceConsolidatedUpdate, PriceConsolidatedFilter


class PriceConsolidatedRepository:
    """Repository for Price Consolidated operations"""

    @staticmethod
    def create(db: Session, price: PriceConsolidatedCreate) -> PriceConsolidated:
        """Create a single price consolidated entry"""
        try:
            db_price = PriceConsolidated(**price.model_dump())
            db.add(db_price)
            db.commit()
            db.refresh(db_price)
            return db_price
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database integrity error: {str(e.orig)}"
            )

    @staticmethod
    def bulk_create(db: Session, entries: List[PriceConsolidatedCreate]) -> dict:
        """
        Bulk create or update price consolidated entries.
        If a product-pricelist combination exists, update it; otherwise create new.
        Returns dict with success status and counts.
        """
        created_count = 0
        updated_count = 0
        failed_count = 0
        errors = []

        for entry in entries:
            try:
                # Check if entry already exists for this product-pricelist combination
                existing = db.query(PriceConsolidated).filter(
                    and_(
                        PriceConsolidated.product == entry.product,
                        PriceConsolidated.pricelist == entry.pricelist
                    )
                ).first()

                if existing:
                    # Update existing entry
                    existing.price = entry.price
                    if entry.gst is not None:
                        existing.gst = entry.gst
                    updated_count += 1
                else:
                    # Create new entry
                    db_price = PriceConsolidated(**entry.model_dump())
                    db.add(db_price)
                    created_count += 1

                db.commit()
            except IntegrityError as e:
                db.rollback()
                failed_count += 1
                errors.append(f"Failed for {entry.product} in {entry.pricelist}: {str(e.orig)}")
            except Exception as e:
                db.rollback()
                failed_count += 1
                errors.append(f"Failed for {entry.product} in {entry.pricelist}: {str(e)}")

        return {
            "success": failed_count == 0,
            "created_count": created_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "errors": errors
        }

    @staticmethod
    def get_by_id(db: Session, price_id: int) -> Optional[PriceConsolidated]:
        """Get price consolidated entry by ID"""
        return db.query(PriceConsolidated).filter(PriceConsolidated.id == price_id).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[PriceConsolidatedFilter] = None
    ) -> Tuple[List[PriceConsolidated], int]:
        """Get all price consolidated entries with optional filters and pagination"""
        query = db.query(PriceConsolidated)

        # Apply filters
        if filters:
            if filters.pricelist:
                query = query.filter(PriceConsolidated.pricelist.ilike(f"%{filters.pricelist}%"))

            if filters.product:
                query = query.filter(PriceConsolidated.product.ilike(f"%{filters.product}%"))

            if filters.min_price is not None:
                query = query.filter(PriceConsolidated.price >= filters.min_price)

            if filters.max_price is not None:
                query = query.filter(PriceConsolidated.price <= filters.max_price)

            if filters.has_gst is not None:
                if filters.has_gst:
                    query = query.filter(PriceConsolidated.gst.isnot(None))
                else:
                    query = query.filter(PriceConsolidated.gst.is_(None))

            if filters.search:
                search_pattern = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        PriceConsolidated.pricelist.ilike(search_pattern),
                        PriceConsolidated.product.ilike(search_pattern)
                    )
                )

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering
        entries = query.order_by(PriceConsolidated.created_at.desc()).offset(skip).limit(limit).all()

        return entries, total

    @staticmethod
    def get_by_pricelist(db: Session, pricelist: str, skip: int = 0, limit: int = 100) -> Tuple[List[PriceConsolidated], int]:
        """Get all price consolidated entries for a specific pricelist"""
        query = db.query(PriceConsolidated).filter(PriceConsolidated.pricelist.ilike(f"%{pricelist}%"))
        total = query.count()
        entries = query.order_by(PriceConsolidated.product).offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_product(db: Session, product: str, skip: int = 0, limit: int = 100) -> Tuple[List[PriceConsolidated], int]:
        """Get all price consolidated entries for a specific product across all pricelists"""
        query = db.query(PriceConsolidated).filter(PriceConsolidated.product.ilike(f"%{product}%"))
        total = query.count()
        entries = query.order_by(PriceConsolidated.pricelist).offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_product_and_pricelist(
        db: Session,
        product: str,
        pricelist: str
    ) -> Optional[PriceConsolidated]:
        """Get price for a specific product in a specific pricelist"""
        return db.query(PriceConsolidated).filter(
            and_(
                PriceConsolidated.product.ilike(f"%{product}%"),
                PriceConsolidated.pricelist.ilike(f"%{pricelist}%")
            )
        ).first()

    @staticmethod
    def lookup_price(db: Session, product: str, pricelist: Optional[str] = None) -> List[PriceConsolidated]:
        """
        Lookup price for a product, optionally filtered by pricelist.
        Returns all matching entries.
        """
        query = db.query(PriceConsolidated).filter(
            PriceConsolidated.product.ilike(f"%{product}%")
        )

        if pricelist:
            query = query.filter(PriceConsolidated.pricelist.ilike(f"%{pricelist}%"))

        return query.all()

    @staticmethod
    def update(db: Session, price_id: int, price_update: PriceConsolidatedUpdate) -> Optional[PriceConsolidated]:
        """Update a price consolidated entry"""
        db_price = PriceConsolidatedRepository.get_by_id(db, price_id)

        if not db_price:
            return None

        # Update only provided fields
        update_data = price_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_price, field, value)

        try:
            db.commit()
            db.refresh(db_price)
            return db_price
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database integrity error: {str(e.orig)}"
            )

    @staticmethod
    def delete(db: Session, price_id: int) -> bool:
        """Delete a price consolidated entry by ID"""
        db_price = PriceConsolidatedRepository.get_by_id(db, price_id)

        if not db_price:
            return False

        db.delete(db_price)
        db.commit()
        return True

    @staticmethod
    def delete_by_pricelist(db: Session, pricelist: str) -> bool:
        """Delete all price entries for a specific pricelist"""
        entries = db.query(PriceConsolidated).filter(
            PriceConsolidated.pricelist.ilike(f"%{pricelist}%")
        ).all()

        if not entries:
            return False

        for entry in entries:
            db.delete(entry)

        db.commit()
        return True

    @staticmethod
    def delete_by_product(db: Session, product: str) -> bool:
        """Delete all price entries for a specific product"""
        entries = db.query(PriceConsolidated).filter(
            PriceConsolidated.product.ilike(f"%{product}%")
        ).all()

        if not entries:
            return False

        for entry in entries:
            db.delete(entry)

        db.commit()
        return True

    # ============================================================================
    # STATISTICS & ANALYTICS
    # ============================================================================

    @staticmethod
    def get_statistics(db: Session) -> dict:
        """Get overall statistics for the price_consolidated table"""
        total_entries = db.query(func.count(PriceConsolidated.id)).scalar()
        unique_pricelists = db.query(func.count(func.distinct(PriceConsolidated.pricelist))).scalar()
        unique_products = db.query(func.count(func.distinct(PriceConsolidated.product))).scalar()
        avg_price = db.query(func.avg(PriceConsolidated.price)).scalar()
        min_price = db.query(func.min(PriceConsolidated.price)).scalar()
        max_price = db.query(func.max(PriceConsolidated.price)).scalar()
        entries_with_gst = db.query(func.count(PriceConsolidated.id)).filter(
            PriceConsolidated.gst.isnot(None)
        ).scalar()

        return {
            "total_entries": total_entries,
            "unique_pricelists": unique_pricelists,
            "unique_products": unique_products,
            "avg_price": float(avg_price) if avg_price else None,
            "min_price": float(min_price) if min_price else None,
            "max_price": float(max_price) if max_price else None,
            "entries_with_gst": entries_with_gst
        }

    @staticmethod
    def group_by_pricelist(db: Session) -> List[dict]:
        """Get entries grouped by pricelist with counts and average price"""
        results = db.query(
            PriceConsolidated.pricelist,
            func.count(PriceConsolidated.id).label('count'),
            func.avg(PriceConsolidated.price).label('avg_price')
        ).group_by(PriceConsolidated.pricelist).order_by(func.count(PriceConsolidated.id).desc()).all()

        return [
            {
                "pricelist": row.pricelist,
                "count": row.count,
                "avg_price": float(row.avg_price) if row.avg_price else None
            }
            for row in results
        ]

    @staticmethod
    def group_by_product(db: Session) -> List[dict]:
        """Get entries grouped by product with min, max, avg prices"""
        results = db.query(
            PriceConsolidated.product,
            func.count(PriceConsolidated.id).label('count'),
            func.min(PriceConsolidated.price).label('min_price'),
            func.max(PriceConsolidated.price).label('max_price'),
            func.avg(PriceConsolidated.price).label('avg_price')
        ).group_by(PriceConsolidated.product).order_by(func.count(PriceConsolidated.id).desc()).all()

        return [
            {
                "product": row.product,
                "count": row.count,
                "min_price": float(row.min_price) if row.min_price else None,
                "max_price": float(row.max_price) if row.max_price else None,
                "avg_price": float(row.avg_price) if row.avg_price else None
            }
            for row in results
        ]

    @staticmethod
    def get_unique_pricelists(db: Session) -> List[str]:
        """Get a list of all unique pricelists"""
        results = db.query(PriceConsolidated.pricelist).distinct().order_by(PriceConsolidated.pricelist).all()
        return [row.pricelist for row in results]

    @staticmethod
    def get_unique_products(db: Session) -> List[str]:
        """Get a list of all unique products"""
        results = db.query(PriceConsolidated.product).distinct().order_by(PriceConsolidated.product).all()
        return [row.product for row in results]

    @staticmethod
    def get_products_by_price_range(
        db: Session,
        min_price: Decimal,
        max_price: Decimal,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[PriceConsolidated], int]:
        """Get products within a specific price range"""
        query = db.query(PriceConsolidated).filter(
            and_(
                PriceConsolidated.price >= min_price,
                PriceConsolidated.price <= max_price
            )
        )
        total = query.count()
        entries = query.order_by(PriceConsolidated.price).offset(skip).limit(limit).all()
        return entries, total
