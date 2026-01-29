"""
Repository layer for Stock Take, Open Stock, and Close Stock operations.
Handles all database queries and operations for the stock take management system.
All operations are date-based and independent.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import date, datetime
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.stock_take import StockTake, OpenStock, CloseStock
from app.models.pos_entry import GeneralNote, Item
from app.models.store_product_flat import StoreProductFlat
from app.schemas.stock_take import (
    StockTakeCreate, StockTakeUpdate,
    OpenStockUpdate, OpenStockEntryBase,
    CloseStockUpdate, CloseStockEntryBase,
)


class StockTakeRepository:
    """Repository for Stock Take operations (simplified - store + date based)"""

    @staticmethod
    def create(db: Session, stock_take: StockTakeCreate) -> StockTake:
        """Create a new stock take or return existing one for same store and date"""
        # Check if stock_take already exists for this store and date
        existing = db.query(StockTake).filter(
            and_(
                StockTake.store_name == stock_take.store_name,
                StockTake.stock_date == stock_take.stock_date
            )
        ).first()

        if existing:
            return existing

        try:
            db_stock_take = StockTake(
                store_name=stock_take.store_name,
                stock_date=stock_take.stock_date
            )
            db.add(db_stock_take)
            db.commit()
            db.refresh(db_stock_take)
            return db_stock_take
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock take already exists for store '{stock_take.store_name}' on date '{stock_take.stock_date}'"
            )

    @staticmethod
    def get_by_id(db: Session, stock_take_id: int) -> Optional[StockTake]:
        """Get stock take by ID"""
        return db.query(StockTake).filter(StockTake.id == stock_take_id).first()

    @staticmethod
    def get_by_store_and_date(db: Session, store_name: str, stock_date: date) -> Optional[StockTake]:
        """Get stock take by store name and date"""
        return db.query(StockTake).filter(
            and_(
                StockTake.store_name == store_name,
                StockTake.stock_date == stock_date
            )
        ).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        store_name: Optional[str] = None,
        stock_status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Tuple[List[StockTake], int]:
        """Get all stock takes with optional filters"""
        query = db.query(StockTake)

        if store_name:
            query = query.filter(StockTake.store_name.ilike(f"%{store_name}%"))
        if stock_status:
            query = query.filter(StockTake.status == stock_status)
        if date_from:
            query = query.filter(StockTake.stock_date >= date_from)
        if date_to:
            query = query.filter(StockTake.stock_date <= date_to)

        total = query.count()
        stock_takes = query.order_by(StockTake.stock_date.desc(), StockTake.store_name)\
            .offset(skip).limit(limit).all()

        return stock_takes, total

    @staticmethod
    def update(db: Session, stock_take_id: int, stock_take_update: StockTakeUpdate) -> Optional[StockTake]:
        """Update stock take status"""
        db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not db_stock_take:
            return None

        update_data = stock_take_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_stock_take, field, value)

        db.commit()
        db.refresh(db_stock_take)
        return db_stock_take

    @staticmethod
    def delete(db: Session, stock_take_id: int) -> bool:
        """Delete stock take"""
        db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not db_stock_take:
            return False

        db.delete(db_stock_take)
        db.commit()
        return True

    @staticmethod
    def complete_stock_take(db: Session, stock_take_id: int) -> Optional[StockTake]:
        """Mark stock take as completed"""
        db_stock_take = StockTakeRepository.get_by_id(db, stock_take_id)
        if not db_stock_take:
            return None

        if db_stock_take.status == 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stock take is already completed"
            )

        db_stock_take.status = 'completed'
        db.commit()
        db.refresh(db_stock_take)
        return db_stock_take


class OpenStockRepository:
    """Repository for Open Stock operations (date-based, independent of stock_take)"""

    @staticmethod
    def bulk_create(db: Session, store_name: str, open_date: date, entries: List[OpenStockEntryBase]) -> List[OpenStock]:
        """
        Create or update multiple open stock entries for a specific store and date.
        If an entry already exists (same store + date + product + promoter), it will be updated.
        """
        created_entries = []
        for entry in entries:
            # Check if entry exists for this store + date + product + promoter
            existing = db.query(OpenStock).filter(
                and_(
                    OpenStock.store_name == store_name,
                    OpenStock.open_date == open_date,
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
                    store_name=store_name,
                    open_date=open_date,
                    product_name=entry.product_name,
                    promoter_name=entry.promoter_name,
                    open_qty=entry.open_qty
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
    def get_by_store_and_date(db: Session, store_name: str, open_date: date) -> List[OpenStock]:
        """Get all open stock entries for a specific store and date"""
        return db.query(OpenStock)\
            .filter(
                and_(
                    OpenStock.store_name == store_name,
                    OpenStock.open_date == open_date
                )
            )\
            .order_by(OpenStock.product_name, OpenStock.promoter_name)\
            .all()

    @staticmethod
    def get_by_store(db: Session, store_name: str, date_from: Optional[date] = None, date_to: Optional[date] = None) -> List[OpenStock]:
        """Get all open stock entries for a store with optional date range filter"""
        query = db.query(OpenStock).filter(OpenStock.store_name == store_name)

        if date_from:
            query = query.filter(OpenStock.open_date >= date_from)
        if date_to:
            query = query.filter(OpenStock.open_date <= date_to)

        return query.order_by(OpenStock.open_date.desc(), OpenStock.product_name, OpenStock.promoter_name).all()

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
                    OpenStock.store_name == db_open_stock.store_name,
                    OpenStock.open_date == db_open_stock.open_date,
                    OpenStock.product_name == product_name,
                    OpenStock.promoter_name == promoter_name,
                    OpenStock.id != open_stock_id
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Open stock entry already exists for product '{product_name}' and promoter '{promoter_name}' on this date"
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
    """Repository for Close Stock operations (date-based, independent of stock_take)"""

    @staticmethod
    def bulk_create(db: Session, store_name: str, close_date: date, entries: List[CloseStockEntryBase]) -> List[CloseStock]:
        """
        Create or update multiple close stock entries for a specific store and date.
        If an entry already exists (same store + date + product + promoter), it will be updated.
        """
        created_entries = []
        for entry in entries:
            # Check if entry exists for this store + date + product + promoter
            existing = db.query(CloseStock).filter(
                and_(
                    CloseStock.store_name == store_name,
                    CloseStock.close_date == close_date,
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
                    store_name=store_name,
                    close_date=close_date,
                    product_name=entry.product_name,
                    promoter_name=entry.promoter_name,
                    close_qty=entry.close_qty
                )
                db.add(db_close_stock)
                created_entries.append(db_close_stock)

        db.commit()
        for entry in created_entries:
            db.refresh(entry)
        return created_entries

    @staticmethod
    def get_by_id(db: Session, close_stock_id: int) -> Optional[CloseStock]:
        """Get close stock entry by ID"""
        return db.query(CloseStock).filter(CloseStock.id == close_stock_id).first()

    @staticmethod
    def get_by_store_and_date(db: Session, store_name: str, close_date: date) -> List[CloseStock]:
        """Get all close stock entries for a specific store and date"""
        return db.query(CloseStock)\
            .filter(
                and_(
                    CloseStock.store_name == store_name,
                    CloseStock.close_date == close_date
                )
            )\
            .order_by(CloseStock.product_name, CloseStock.promoter_name)\
            .all()

    @staticmethod
    def get_by_store(db: Session, store_name: str, date_from: Optional[date] = None, date_to: Optional[date] = None) -> List[CloseStock]:
        """Get all close stock entries for a store with optional date range filter"""
        query = db.query(CloseStock).filter(CloseStock.store_name == store_name)

        if date_from:
            query = query.filter(CloseStock.close_date >= date_from)
        if date_to:
            query = query.filter(CloseStock.close_date <= date_to)

        return query.order_by(CloseStock.close_date.desc(), CloseStock.product_name, CloseStock.promoter_name).all()

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
                    CloseStock.store_name == db_close_stock.store_name,
                    CloseStock.close_date == db_close_stock.close_date,
                    CloseStock.product_name == product_name,
                    CloseStock.promoter_name == promoter_name,
                    CloseStock.id != close_stock_id
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Close stock entry already exists for product '{product_name}' and promoter '{promoter_name}' on this date"
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


class StockTakeSummaryRepository:
    """Repository for linked Stock Take Summary operations"""

    @staticmethod
    def get_summary_by_store(
        db: Session,
        store_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get linked stock take summary for a store.
        Links open_stock, close_stock, and POS sales by store_name.
        - start_date: Filter by created_at/note_date >= start_date
        - end_date: Filter by created_at/note_date <= end_date

        Returns:
            Dictionary with store_name, start_date (earliest open_stock.created_at),
            end_date (latest close_stock.created_at), all entries, and POS sales.
        """
        # Query open stock entries for this store
        open_query = db.query(OpenStock).filter(OpenStock.store_name == store_name)
        if start_date:
            open_query = open_query.filter(OpenStock.created_at >= start_date)
        if end_date:
            open_query = open_query.filter(OpenStock.created_at <= end_date)

        open_entries = open_query.order_by(OpenStock.created_at, OpenStock.product_name).all()

        # Query close stock entries for this store
        close_query = db.query(CloseStock).filter(CloseStock.store_name == store_name)
        if start_date:
            close_query = close_query.filter(CloseStock.created_at >= start_date)
        if end_date:
            close_query = close_query.filter(CloseStock.created_at <= end_date)

        close_entries = close_query.order_by(CloseStock.created_at, CloseStock.product_name).all()

        # Query POS sales from items table - aggregate quantity by product
        pos_query = db.query(
            Item.product.label('product_name'),
            func.sum(Item.quantity).label('total_quantity')
        ).join(
            GeneralNote, Item.general_note_id == GeneralNote.id
        ).filter(
            Item.store_name == store_name
        )

        if start_date:
            pos_query = pos_query.filter(GeneralNote.note_date >= start_date.date() if isinstance(start_date, datetime) else start_date)
        if end_date:
            pos_query = pos_query.filter(GeneralNote.note_date <= end_date.date() if isinstance(end_date, datetime) else end_date)

        pos_sales_result = pos_query.group_by(Item.product).all()

        # Convert to dict: {product_name: quantity}
        pos_sales = {
            sale.product_name: float(sale.total_quantity) if sale.total_quantity else 0.0
            for sale in pos_sales_result
        }

        # Get earliest created_at from open_stock (start_date)
        earliest_open = db.query(func.min(OpenStock.created_at))\
            .filter(OpenStock.store_name == store_name).scalar()

        # Get latest created_at from close_stock (end_date)
        latest_close = db.query(func.max(CloseStock.created_at))\
            .filter(CloseStock.store_name == store_name).scalar()

        return {
            "store_name": store_name,
            "start_date": earliest_open,
            "end_date": latest_close,
            "open_stock_entries": open_entries,
            "close_stock_entries": close_entries,
            "pos_sales": pos_sales,
            "total_open_stock": len(open_entries),
            "total_close_stock": len(close_entries)
        }

    @staticmethod
    def get_all_stores_with_stock(db: Session) -> List[str]:
        """Get list of all stores that have open or close stock entries"""
        open_stores = db.query(OpenStock.store_name).distinct().all()
        close_stores = db.query(CloseStock.store_name).distinct().all()

        all_stores = set([s[0] for s in open_stores] + [s[0] for s in close_stores])
        return sorted(list(all_stores))


class StockVarianceRepository:
    """Repository for Stock Variance Report operations"""

    @staticmethod
    def get_all_variance_data(
        db: Session,
        store_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all stock variance data (no date filter).
        If store_name is None, returns data from all stores.

        Returns:
            List of all variance items
        """
        return StockVarianceRepository._get_variance_data(db, store_name, None, None)

    @staticmethod
    def get_variance_data_by_date_range(
        db: Session,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get stock variance data within a date range (all stores).
        Uses created_at timestamps for filtering.

        Args:
            db: Database session
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)

        Returns:
            List of variance items within the date range
        """
        return StockVarianceRepository._get_variance_data(db, None, start_date, end_date)

    @staticmethod
    def _get_variance_data(
        db: Session,
        store_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Internal method to get variance data.
        Links open_stock, close_stock, store_product, and POS sales by product.

        Args:
            db: Database session
            store_name: Store name (None for all stores)
            start_date: Optional start datetime filter (uses created_at)
            end_date: Optional end datetime filter (uses created_at)

        Returns:
            List of variance items
        """
        # Query open stock entries
        open_query = db.query(OpenStock)
        if store_name:
            open_query = open_query.filter(OpenStock.store_name == store_name)
        if start_date:
            open_query = open_query.filter(OpenStock.created_at >= start_date)
        if end_date:
            open_query = open_query.filter(OpenStock.created_at <= end_date)

        open_entries = open_query.all()

        # Query close stock entries
        close_query = db.query(CloseStock)
        if store_name:
            close_query = close_query.filter(CloseStock.store_name == store_name)
        if start_date:
            close_query = close_query.filter(CloseStock.created_at >= start_date)
        if end_date:
            close_query = close_query.filter(CloseStock.created_at <= end_date)

        close_entries = close_query.all()

        # Create lookup dictionaries
        # Key: (store_name, product_name), Value: {open_qty, open_created_at}
        open_lookup = {}
        for entry in open_entries:
            key = (entry.store_name, entry.product_name)
            if key not in open_lookup:
                open_lookup[key] = {
                    'open_qty': entry.open_qty,
                    'created_at': entry.created_at,
                    'store_name': entry.store_name
                }
            else:
                # Sum quantities if multiple entries for same product
                open_lookup[key]['open_qty'] += entry.open_qty
                # Keep earliest created_at
                if entry.created_at < open_lookup[key]['created_at']:
                    open_lookup[key]['created_at'] = entry.created_at

        # Key: (store_name, product_name), Value: {close_qty, close_created_at}
        close_lookup = {}
        for entry in close_entries:
            key = (entry.store_name, entry.product_name)
            if key not in close_lookup:
                close_lookup[key] = {
                    'close_qty': entry.close_qty,
                    'created_at': entry.created_at,
                    'store_name': entry.store_name
                }
            else:
                # Sum quantities if multiple entries for same product
                close_lookup[key]['close_qty'] += entry.close_qty
                # Keep latest created_at
                if entry.created_at > close_lookup[key]['created_at']:
                    close_lookup[key]['created_at'] = entry.created_at

        # Get all unique (store, product) combinations
        all_keys = set(open_lookup.keys()) | set(close_lookup.keys())

        if not all_keys:
            return []

        # Get unique products and stores
        all_products = set(k[1] for k in all_keys)
        all_stores = set(k[0] for k in all_keys)

        # Query store_product for ykey and unit_of_measure
        store_product_query = db.query(
            StoreProductFlat.product_name,
            StoreProductFlat.store,
            StoreProductFlat.ykey,
            StoreProductFlat.unit_of_measure
        ).filter(
            StoreProductFlat.product_name.in_(list(all_products))
        )
        if store_name:
            store_product_query = store_product_query.filter(StoreProductFlat.store == store_name)
        else:
            store_product_query = store_product_query.filter(StoreProductFlat.store.in_(list(all_stores)))

        store_product_results = store_product_query.all()

        # Create store_product lookup: (store, product) -> {ykey, unit_of_measure}
        store_product_lookup = {
            (sp.store, sp.product_name): {'ykey': sp.ykey, 'unit_of_measure': sp.unit_of_measure}
            for sp in store_product_results
        }

        # Query POS sales from items table - aggregate quantity by store and product
        pos_query = db.query(
            Item.store_name,
            Item.product.label('product_name'),
            func.sum(Item.quantity).label('total_quantity')
        ).join(
            GeneralNote, Item.general_note_id == GeneralNote.id
        )

        if store_name:
            pos_query = pos_query.filter(Item.store_name == store_name)
        else:
            pos_query = pos_query.filter(Item.store_name.in_(list(all_stores)))

        if start_date:
            pos_query = pos_query.filter(GeneralNote.note_date >= start_date.date())
        if end_date:
            pos_query = pos_query.filter(GeneralNote.note_date <= end_date.date())

        pos_sales_result = pos_query.group_by(Item.store_name, Item.product).all()

        # Create POS sales lookup: (store, product) -> quantity
        pos_sales_lookup = {
            (sale.store_name, sale.product_name): float(sale.total_quantity) if sale.total_quantity else 0.0
            for sale in pos_sales_result
        }

        # Build variance report data
        variance_data = []
        # Sort keys handling None values (None store names come first)
        sorted_keys = sorted(all_keys, key=lambda x: (x[0] or '', x[1] or ''))
        for key in sorted_keys:
            store, product_name = key
            open_data = open_lookup.get(key, {'open_qty': 0, 'created_at': None, 'store_name': store})
            close_data = close_lookup.get(key, {'close_qty': 0, 'created_at': None, 'store_name': store})
            store_product = store_product_lookup.get(key, {'ykey': None, 'unit_of_measure': None})

            open_qty = open_data['open_qty']
            close_qty = close_data['close_qty']
            difference_qty = abs(open_qty - close_qty)
            pos_total_sale = pos_sales_lookup.get(key, 0.0)
            variance = difference_qty - pos_total_sale

            # Use created_at timestamps or current time as fallback, then convert to date
            start_timestamp = open_data['created_at'] or datetime.now()
            end_timestamp = close_data['created_at'] or datetime.now()

            # Convert datetime to date for the response
            start_date_value = start_timestamp.date() if isinstance(start_timestamp, datetime) else start_timestamp
            end_date_value = end_timestamp.date() if isinstance(end_timestamp, datetime) else end_timestamp

            variance_data.append({
                'store_name': store or '',
                'start_date': start_date_value,
                'end_date': end_date_value,
                'product': product_name,
                'unit_of_measure': store_product['unit_of_measure'],
                'ykey': store_product['ykey'],
                'open_qty': open_qty,
                'close_qty': close_qty,
                'difference_qty': difference_qty,
                'pos_total_sale': pos_total_sale,
                'variance': variance
            })

        return variance_data
