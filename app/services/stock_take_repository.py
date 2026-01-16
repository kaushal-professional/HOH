"""
Repository layer for Stock Take, Open Stock, and Close Stock operations.
Handles all database queries and operations for the stock take management system.
"""

from typing import List, Optional, Tuple
from uuid import UUID
from datetime import date
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.stock_take import StockTake, OpenStock, CloseStock
from app.schemas.stock_take import (
    StockTakeCreate, StockTakeUpdate,
    OpenStockCreate, OpenStockUpdate,
    CloseStockCreate, CloseStockUpdate,
)


class StockTakeRepository:
    """Repository for Stock Take operations"""

    @staticmethod
    def create(db: Session, stock_take: StockTakeCreate) -> StockTake:
        """Create a new stock take with optional open stock entries, or reuse existing one for same store"""
        try:
            # Check if active stock_take already exists for this store
            existing_stock_take = db.query(StockTake).filter(
                StockTake.store_name == stock_take.store_name,
                StockTake.status == 'active'
            ).first()

            if existing_stock_take:
                # Reuse existing stock_take UUID
                db_stock_take = existing_stock_take
                
                # Add new open stock entries to the existing stock_take if provided
                if stock_take.open_stock_entries:
                    for entry in stock_take.open_stock_entries:
                        # Check if entry already exists to avoid duplicates
                        existing_entry = db.query(OpenStock).filter(
                            and_(
                                OpenStock.stock_take_id == db_stock_take.stock_take_id,
                                OpenStock.product_name == entry.product_name,
                                OpenStock.promoter_name == entry.promoter_name
                            )
                        ).first()
                        
                        if existing_entry:
                            # Update existing entry
                            existing_entry.open_qty = entry.open_qty
                        else:
                            # Create new entry
                            open_stock = OpenStock(
                                stock_take_id=db_stock_take.stock_take_id,
                                **entry.model_dump()
                            )
                            db.add(open_stock)
                    
                    db.flush()
                    
                    # Update start_date from earliest open_stock created_at
                    earliest_open_stock = db.query(OpenStock).filter(
                        OpenStock.stock_take_id == db_stock_take.stock_take_id
                    ).order_by(OpenStock.created_at.asc()).first()
                    
                    if earliest_open_stock:
                        db_stock_take.start_date = earliest_open_stock.created_at.date()
            else:
                # Create new stock take with placeholder date (will be updated after open_stock is created)
                from datetime import datetime
                stock_take_data = stock_take.model_dump(exclude={'open_stock_entries'})
                stock_take_data['start_date'] = datetime.now().date()  # Temporary value
                db_stock_take = StockTake(**stock_take_data)
                db.add(db_stock_take)
                db.flush()  # Flush to get the stock_take_id

                # Create open stock entries if provided
                if stock_take.open_stock_entries:
                    for entry in stock_take.open_stock_entries:
                        # Check if entry already exists to avoid duplicates
                        existing_entry = db.query(OpenStock).filter(
                            and_(
                                OpenStock.stock_take_id == db_stock_take.stock_take_id,
                                OpenStock.product_name == entry.product_name,
                                OpenStock.promoter_name == entry.promoter_name
                            )
                        ).first()

                        if not existing_entry:
                            # Only create if it doesn't exist
                            open_stock = OpenStock(
                                stock_take_id=db_stock_take.stock_take_id,
                                **entry.model_dump()
                            )
                            db.add(open_stock)
                    
                    db.flush()
                    
                    # Update start_date from earliest open_stock created_at
                    earliest_open_stock = db.query(OpenStock).filter(
                        OpenStock.stock_take_id == db_stock_take.stock_take_id
                    ).order_by(OpenStock.created_at.asc()).first()
                    
                    if earliest_open_stock:
                        db_stock_take.start_date = earliest_open_stock.created_at.date()

            db.commit()
            db.refresh(db_stock_take)
            return db_stock_take
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database integrity error: {str(e.orig)}"
            )

    @staticmethod
    def get_by_id(db: Session, stock_take_id: UUID) -> Optional[StockTake]:
        """Get stock take by ID"""
        return db.query(StockTake).filter(StockTake.stock_take_id == stock_take_id).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        store_name: Optional[str] = None,
        status: Optional[str] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None
    ) -> Tuple[List[StockTake], int]:
        """Get all stock takes with optional filters"""
        query = db.query(StockTake)

        # Apply filters
        if store_name:
            query = query.filter(StockTake.store_name.ilike(f"%{store_name}%"))
        if status:
            query = query.filter(StockTake.status == status)
        if start_date_from:
            query = query.filter(StockTake.start_date >= start_date_from)
        if start_date_to:
            query = query.filter(StockTake.start_date <= start_date_to)

        # Get total count
        total = query.count()

        # Get paginated results with related stocks
        stock_takes = query.options(joinedload(StockTake.open_stocks))\
            .options(joinedload(StockTake.close_stocks))\
            .order_by(StockTake.created_at.desc())\
            .offset(skip).limit(limit).all()

        return stock_takes, total

    @staticmethod
    def update(db: Session, stock_take_id: UUID, stock_take_update: StockTakeUpdate) -> Optional[StockTake]:
        """Update stock take"""
        db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not db_stock_take:
            return None

        update_data = stock_take_update.model_dump(exclude_unset=True)

        # Validate end_date if being updated
        if 'end_date' in update_data and update_data['end_date']:
            start_date = update_data.get('start_date', db_stock_take.start_date)
            if update_data['end_date'] < start_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="End date must be greater than or equal to start date"
                )

        for field, value in update_data.items():
            setattr(db_stock_take, field, value)

        db.commit()
        db.refresh(db_stock_take)
        return db_stock_take

    @staticmethod
    def delete(db: Session, stock_take_id: UUID) -> bool:
        """Delete stock take (cascade deletes open and close stocks)"""
        db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not db_stock_take:
            return False

        db.delete(db_stock_take)
        db.commit()
        return True

    @staticmethod
    def complete_stock_take(db: Session, stock_take_id: UUID) -> Optional[StockTake]:
        """Mark stock take as completed and set end_date to today if not set"""
        db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not db_stock_take:
            return None

        if db_stock_take.status == 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stock take is already completed"
            )

        db_stock_take.status = 'completed'
        if not db_stock_take.end_date:
            db_stock_take.end_date = date.today()

        db.commit()
        db.refresh(db_stock_take)
        return db_stock_take

    @staticmethod
    def get_summary(db: Session, stock_take_id: UUID) -> Optional[StockTake]:
        """Get stock take with all open and close stocks"""
        return db.query(StockTake)\
            .options(joinedload(StockTake.open_stocks))\
            .options(joinedload(StockTake.close_stocks))\
            .filter(StockTake.stock_take_id == stock_take_id)\
            .first()


class OpenStockRepository:
    """Repository for Open Stock operations"""

    @staticmethod
    def create(db: Session, stock_take_id: UUID, open_stock: OpenStockCreate) -> OpenStock:
        """Create a single open stock entry"""
        # Verify stock take exists
        stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not stock_take:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock take with ID {stock_take_id} not found"
            )

        try:
            db_open_stock = OpenStock(
                stock_take_id=stock_take_id,
                **open_stock.model_dump()
            )
            db.add(db_open_stock)
            db.commit()
            db.refresh(db_open_stock)
            return db_open_stock
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Open stock entry already exists for product '{open_stock.product_name}' and promoter '{open_stock.promoter_name}'"
            )

    @staticmethod
    def bulk_create(db: Session, stock_take_id: UUID, entries: List[OpenStockCreate]) -> List[OpenStock]:
        """Create or update multiple open stock entries"""
        # Verify stock take exists
        stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not stock_take:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock take with ID {stock_take_id} not found"
            )

        created_entries = []
        for entry in entries:
            # Check if entry exists
            existing = db.query(OpenStock).filter(
                and_(
                    OpenStock.stock_take_id == stock_take_id,
                    OpenStock.product_name == entry.product_name,
                    OpenStock.promoter_name == entry.promoter_name
                )
            ).first()

            if existing:
                # Update existing entry
                existing.open_qty = entry.open_qty
                created_entries.append(existing)
            else:
                # Create new entry
                db_open_stock = OpenStock(
                    stock_take_id=stock_take_id,
                    **entry.model_dump()
                )
                db.add(db_open_stock)
                created_entries.append(db_open_stock)

        db.commit()
        for entry in created_entries:
            db.refresh(entry)
        return created_entries

    @staticmethod
    def get_by_id(db: Session, open_stock_id: int) -> Optional[OpenStock]:
        """Get open stock entry by ID"""
        return db.query(OpenStock).filter(OpenStock.id == open_stock_id).first()

    @staticmethod
    def get_by_stock_take(db: Session, stock_take_id: UUID) -> List[OpenStock]:
        """Get all open stock entries for a stock take"""
        return db.query(OpenStock)\
            .filter(OpenStock.stock_take_id == stock_take_id)\
            .order_by(OpenStock.product_name, OpenStock.promoter_name)\
            .all()

    @staticmethod
    def update(db: Session, open_stock_id: int, open_stock_update: OpenStockUpdate) -> Optional[OpenStock]:
        """Update open stock entry"""
        db_open_stock = OpenStockRepository.get_by_id(db, open_stock_id)
        if not db_open_stock:
            return None

        update_data = open_stock_update.model_dump(exclude_unset=True)

        # Check for duplicate if product_name or promoter_name is being updated
        if 'product_name' in update_data or 'promoter_name' in update_data:
            product_name = update_data.get('product_name', db_open_stock.product_name)
            promoter_name = update_data.get('promoter_name', db_open_stock.promoter_name)

            existing = db.query(OpenStock).filter(
                and_(
                    OpenStock.stock_take_id == db_open_stock.stock_take_id,
                    OpenStock.product_name == product_name,
                    OpenStock.promoter_name == promoter_name,
                    OpenStock.id != open_stock_id
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Open stock entry already exists for product '{product_name}' and promoter '{promoter_name}'"
                )

        for field, value in update_data.items():
            setattr(db_open_stock, field, value)

        db.commit()
        db.refresh(db_open_stock)
        return db_open_stock

    @staticmethod
    def delete(db: Session, open_stock_id: int) -> bool:
        """Delete open stock entry"""
        db_open_stock = OpenStockRepository.get_by_id(db, open_stock_id)
        if not db_open_stock:
            return False

        db.delete(db_open_stock)
        db.commit()
        return True


class CloseStockRepository:
    """Repository for Close Stock operations"""

    @staticmethod
    def create(db: Session, stock_take_id: UUID, close_stock: CloseStockCreate) -> CloseStock:
        """Create a single close stock entry and auto-update end_date from created_at"""
        # Verify stock take exists
        stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not stock_take:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock take with ID {stock_take_id} not found"
            )

        try:
            db_close_stock = CloseStock(
                stock_take_id=stock_take_id,
                **close_stock.model_dump()
            )
            db.add(db_close_stock)
            db.flush()
            
            # Update end_date from earliest close_stock created_at timestamp
            earliest_close_stock = db.query(CloseStock).filter(
                CloseStock.stock_take_id == stock_take_id
            ).order_by(CloseStock.created_at.asc()).first()
            
            if earliest_close_stock:
                stock_take.end_date = earliest_close_stock.created_at.date()
                stock_take.status = 'completed'
            
            db.commit()
            db.refresh(db_close_stock)
            return db_close_stock
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Close stock entry already exists for product '{close_stock.product_name}' and promoter '{close_stock.promoter_name}'"
            )

    @staticmethod
    def bulk_create(db: Session, stock_take_id: UUID, entries: List[CloseStockCreate]) -> List[CloseStock]:
        """Create or update multiple close stock entries and auto-update end_date"""
        # Verify stock take exists
        stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not stock_take:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock take with ID {stock_take_id} not found"
            )

        created_entries = []
        for entry in entries:
            # Check if entry exists
            existing = db.query(CloseStock).filter(
                and_(
                    CloseStock.stock_take_id == stock_take_id,
                    CloseStock.product_name == entry.product_name,
                    CloseStock.promoter_name == entry.promoter_name
                )
            ).first()

            if existing:
                # Update existing entry
                existing.close_qty = entry.close_qty
                created_entries.append(existing)
            else:
                # Create new entry
                db_close_stock = CloseStock(
                    stock_take_id=stock_take_id,
                    **entry.model_dump()
                )
                db.add(db_close_stock)
                created_entries.append(db_close_stock)

        db.flush()
        
        # Update end_date from earliest close_stock created_at timestamp
        earliest_close_stock = db.query(CloseStock).filter(
            CloseStock.stock_take_id == stock_take_id
        ).order_by(CloseStock.created_at.asc()).first()
        
        if earliest_close_stock:
            stock_take.end_date = earliest_close_stock.created_at.date()
            stock_take.status = 'completed'

        db.commit()
        for entry in created_entries:
            db.refresh(entry)
        return created_entries

    @staticmethod
    def get_by_id(db: Session, close_stock_id: int) -> Optional[CloseStock]:
        """Get close stock entry by ID"""
        return db.query(CloseStock).filter(CloseStock.id == close_stock_id).first()

    @staticmethod
    def get_by_stock_take(db: Session, stock_take_id: UUID) -> List[CloseStock]:
        """Get all close stock entries for a stock take"""
        return db.query(CloseStock)\
            .filter(CloseStock.stock_take_id == stock_take_id)\
            .order_by(CloseStock.product_name, CloseStock.promoter_name)\
            .all()

    @staticmethod
    def update(db: Session, close_stock_id: int, close_stock_update: CloseStockUpdate) -> Optional[CloseStock]:
        """Update close stock entry"""
        db_close_stock = CloseStockRepository.get_by_id(db, close_stock_id)
        if not db_close_stock:
            return None

        update_data = close_stock_update.model_dump(exclude_unset=True)

        # Check for duplicate if product_name or promoter_name is being updated
        if 'product_name' in update_data or 'promoter_name' in update_data:
            product_name = update_data.get('product_name', db_close_stock.product_name)
            promoter_name = update_data.get('promoter_name', db_close_stock.promoter_name)

            existing = db.query(CloseStock).filter(
                and_(
                    CloseStock.stock_take_id == db_close_stock.stock_take_id,
                    CloseStock.product_name == product_name,
                    CloseStock.promoter_name == promoter_name,
                    CloseStock.id != close_stock_id
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Close stock entry already exists for product '{product_name}' and promoter '{promoter_name}'"
                )

        for field, value in update_data.items():
            setattr(db_close_stock, field, value)

        db.commit()
        db.refresh(db_close_stock)
        return db_close_stock

    @staticmethod
    def delete(db: Session, close_stock_id: int) -> bool:
        """Delete close stock entry"""
        db_close_stock = CloseStockRepository.get_by_id(db, close_stock_id)
        if not db_close_stock:
            return False

        db.delete(db_close_stock)
        db.commit()
        return True
