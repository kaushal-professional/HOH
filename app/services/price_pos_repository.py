"""
Repository layer for Price POS operations.
Handles all database queries and operations for the price_pos table.
"""

from typing import List, Optional, Tuple
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.price_pos import PricePos
from app.schemas.price_pos import PricePosCreate, PricePosUpdate, PricePosFilter


class PricePosRepository:
    """Repository for Price POS operations"""

    @staticmethod
    def create(db: Session, price_pos: PricePosCreate) -> PricePos:
        """Create a single price POS entry"""
        try:
            db_price_pos = PricePos(**price_pos.model_dump())
            db.add(db_price_pos)
            db.commit()
            db.refresh(db_price_pos)
            return db_price_pos
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database integrity error: {str(e.orig)}"
            )

    @staticmethod
    def bulk_create(db: Session, entries: List[PricePosCreate]) -> dict:
        """
        Bulk create price POS entries.
        Returns dict with success status and counts.
        """
        created_count = 0
        failed_count = 0
        errors = []

        for entry in entries:
            try:
                db_price_pos = PricePos(**entry.model_dump())
                db.add(db_price_pos)
                db.commit()
                created_count += 1
            except IntegrityError as e:
                db.rollback()
                failed_count += 1
                errors.append(f"Failed to create entry for {entry.point_of_sale}: {str(e.orig)}")
            except Exception as e:
                db.rollback()
                failed_count += 1
                errors.append(f"Failed to create entry for {entry.point_of_sale}: {str(e)}")

        return {
            "success": failed_count == 0,
            "created_count": created_count,
            "failed_count": failed_count,
            "errors": errors
        }

    @staticmethod
    def get_by_id(db: Session, price_pos_id: int) -> Optional[PricePos]:
        """Get price POS entry by ID"""
        return db.query(PricePos).filter(PricePos.id == price_pos_id).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[PricePosFilter] = None
    ) -> Tuple[List[PricePos], int]:
        """Get all price POS entries with optional filters and pagination"""
        query = db.query(PricePos)

        # Apply filters
        if filters:
            if filters.state:
                query = query.filter(PricePos.state.ilike(f"%{filters.state}%"))

            if filters.point_of_sale:
                query = query.filter(PricePos.point_of_sale.ilike(f"%{filters.point_of_sale}%"))

            if filters.promoter:
                query = query.filter(PricePos.promoter.ilike(f"%{filters.promoter}%"))

            if filters.pricelist:
                query = query.filter(PricePos.pricelist.ilike(f"%{filters.pricelist}%"))

            if filters.search:
                search_pattern = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        PricePos.state.ilike(search_pattern),
                        PricePos.point_of_sale.ilike(search_pattern),
                        PricePos.promoter.ilike(search_pattern),
                        PricePos.pricelist.ilike(search_pattern)
                    )
                )

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering
        entries = query.order_by(PricePos.created_at.desc()).offset(skip).limit(limit).all()

        return entries, total

    @staticmethod
    def get_by_state(db: Session, state: str, skip: int = 0, limit: int = 100) -> Tuple[List[PricePos], int]:
        """Get all price POS entries for a specific state"""
        query = db.query(PricePos).filter(PricePos.state.ilike(f"%{state}%"))
        total = query.count()
        entries = query.order_by(PricePos.created_at.desc()).offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_point_of_sale(db: Session, point_of_sale: str, skip: int = 0, limit: int = 100) -> Tuple[List[PricePos], int]:
        """Get all price POS entries for a specific point of sale"""
        query = db.query(PricePos).filter(PricePos.point_of_sale.ilike(f"%{point_of_sale}%"))
        total = query.count()
        entries = query.order_by(PricePos.created_at.desc()).offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_promoter(db: Session, promoter: str, skip: int = 0, limit: int = 100) -> Tuple[List[PricePos], int]:
        """Get all price POS entries for a specific promoter"""
        query = db.query(PricePos).filter(PricePos.promoter.ilike(f"%{promoter}%"))
        total = query.count()
        entries = query.order_by(PricePos.created_at.desc()).offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def get_by_pricelist(db: Session, pricelist: str, skip: int = 0, limit: int = 100) -> Tuple[List[PricePos], int]:
        """Get all price POS entries for a specific pricelist"""
        query = db.query(PricePos).filter(PricePos.pricelist.ilike(f"%{pricelist}%"))
        total = query.count()
        entries = query.order_by(PricePos.created_at.desc()).offset(skip).limit(limit).all()
        return entries, total

    @staticmethod
    def update(db: Session, price_pos_id: int, price_pos_update: PricePosUpdate) -> Optional[PricePos]:
        """Update a price POS entry"""
        db_price_pos = PricePosRepository.get_by_id(db, price_pos_id)

        if not db_price_pos:
            return None

        # Update only provided fields
        update_data = price_pos_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_price_pos, field, value)

        try:
            db.commit()
            db.refresh(db_price_pos)
            return db_price_pos
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database integrity error: {str(e.orig)}"
            )

    @staticmethod
    def delete(db: Session, price_pos_id: int) -> bool:
        """Delete a price POS entry by ID"""
        db_price_pos = PricePosRepository.get_by_id(db, price_pos_id)

        if not db_price_pos:
            return False

        db.delete(db_price_pos)
        db.commit()
        return True

    @staticmethod
    def delete_by_point_of_sale(db: Session, point_of_sale: str) -> bool:
        """Delete all price POS entries for a specific point of sale"""
        entries = db.query(PricePos).filter(
            PricePos.point_of_sale.ilike(f"%{point_of_sale}%")
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
        """Get overall statistics for the price_pos table"""
        total_entries = db.query(func.count(PricePos.id)).scalar()
        unique_states = db.query(func.count(func.distinct(PricePos.state))).scalar()
        unique_pos = db.query(func.count(func.distinct(PricePos.point_of_sale))).scalar()
        unique_promoters = db.query(func.count(func.distinct(PricePos.promoter))).scalar()
        unique_pricelists = db.query(func.count(func.distinct(PricePos.pricelist))).scalar()

        return {
            "total_entries": total_entries,
            "unique_states": unique_states,
            "unique_pos": unique_pos,
            "unique_promoters": unique_promoters,
            "unique_pricelists": unique_pricelists
        }

    @staticmethod
    def group_by_state(db: Session) -> List[dict]:
        """Get entries grouped by state with counts"""
        results = db.query(
            PricePos.state,
            func.count(PricePos.id).label('count')
        ).group_by(PricePos.state).order_by(func.count(PricePos.id).desc()).all()

        return [{"state": row.state, "count": row.count} for row in results]

    @staticmethod
    def group_by_promoter(db: Session) -> List[dict]:
        """Get entries grouped by promoter with counts"""
        results = db.query(
            PricePos.promoter,
            func.count(PricePos.id).label('count')
        ).group_by(PricePos.promoter).order_by(func.count(PricePos.id).desc()).all()

        return [{"promoter": row.promoter, "count": row.count} for row in results]

    @staticmethod
    def group_by_pricelist(db: Session) -> List[dict]:
        """Get entries grouped by pricelist with counts"""
        results = db.query(
            PricePos.pricelist,
            func.count(PricePos.id).label('count')
        ).group_by(PricePos.pricelist).order_by(func.count(PricePos.id).desc()).all()

        return [{"pricelist": row.pricelist, "count": row.count} for row in results]

    @staticmethod
    def get_unique_states(db: Session) -> List[str]:
        """Get a list of all unique states"""
        results = db.query(PricePos.state).distinct().order_by(PricePos.state).all()
        return [row.state for row in results]

    @staticmethod
    def get_unique_point_of_sales(db: Session) -> List[str]:
        """Get a list of all unique points of sale"""
        results = db.query(PricePos.point_of_sale).distinct().order_by(PricePos.point_of_sale).all()
        return [row.point_of_sale for row in results]

    @staticmethod
    def get_unique_promoters(db: Session) -> List[str]:
        """Get a list of all unique promoters"""
        results = db.query(PricePos.promoter).distinct().order_by(PricePos.promoter).all()
        return [row.promoter for row in results]

    @staticmethod
    def get_unique_pricelists(db: Session) -> List[str]:
        """Get a list of all unique pricelists"""
        results = db.query(PricePos.pricelist).distinct().order_by(PricePos.pricelist).all()
        return [row.pricelist for row in results]
