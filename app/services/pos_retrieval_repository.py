"""
Repository layer for POS Data Retrieval operations.
Handles fetching POS data from general_notes, barcodes, barcode_products tables
with ykey and unit_of_measurement from store_product table.
"""

from typing import List, Tuple, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import and_, func, cast, Date
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.pos_entry import GeneralNote, Barcode, BarcodeProduct
from app.models.store_product_flat import StoreProductFlat


class POSRetrievalRepository:
    """Repository for POS data retrieval operations"""

    @staticmethod
    def _build_pos_data_query(db: Session):
        """
        Build the base query for POS data retrieval.
        Joins barcode_products -> barcodes -> general_notes and
        left joins store_product for ykey and unit_of_measure.
        """
        # Subquery to get ykey and unit_of_measure from store_product
        # Match by product_name and store
        store_product_subq = db.query(
            StoreProductFlat.product_name,
            StoreProductFlat.store,
            StoreProductFlat.ykey,
            StoreProductFlat.unit_of_measure
        ).subquery()

        # Main query joining all tables
        query = db.query(
            BarcodeProduct.id,
            GeneralNote.note_date.label('date'),
            GeneralNote.promoter_name,
            Barcode.page_number,
            Barcode.count.label('barcode_count'),
            BarcodeProduct.store_name,
            store_product_subq.c.ykey,
            BarcodeProduct.product.label('product_name'),
            store_product_subq.c.unit_of_measure.label('unit_of_measurement'),
            BarcodeProduct.weight.label('quantity'),
            BarcodeProduct.price.label('unit_price'),
            BarcodeProduct.gst.label('taxes'),
            BarcodeProduct.price.label('price_excluding_tax'),
            BarcodeProduct.price_with_gst.label('price_including_tax'),
            BarcodeProduct.created_at
        ).join(
            Barcode, BarcodeProduct.barcode_id == Barcode.id
        ).join(
            GeneralNote, Barcode.general_note_id == GeneralNote.id
        ).outerjoin(
            store_product_subq,
            and_(
                store_product_subq.c.product_name == BarcodeProduct.product,
                store_product_subq.c.store == BarcodeProduct.store_name
            )
        )

        return query

    @staticmethod
    def get_pos_data(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        store_name: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated POS data.

        Args:
            db: Database session
            page: Page number (1-indexed)
            page_size: Number of records per page
            store_name: Optional filter by store name

        Returns:
            Tuple of (list of POS data items, total count)
        """
        query = POSRetrievalRepository._build_pos_data_query(db)

        # Apply store filter if provided
        if store_name:
            query = query.filter(BarcodeProduct.store_name.ilike(f"%{store_name}%"))

        # Order by created_at descending (newest first)
        query = query.order_by(BarcodeProduct.created_at.desc())

        # Get total count
        total = query.count()

        # Apply pagination
        skip = (page - 1) * page_size
        results = query.offset(skip).limit(page_size).all()

        # Convert to list of dicts
        data = []
        for row in results:
            # Format general_note with promoter name and barcode count per page
            general_note = f"Promoter: {row.promoter_name} | Page {row.page_number}: {row.barcode_count} barcodes"
            data.append({
                'id': row.id,
                'date': row.date,
                'general_note': general_note,
                'store_name': row.store_name,
                'ykey': row.ykey,
                'product_name': row.product_name,
                'unit_of_measurement': row.unit_of_measurement,
                'quantity': row.quantity,
                'unit_price': row.unit_price,
                'taxes': row.taxes,
                'price_excluding_tax': row.price_excluding_tax,
                'price_including_tax': row.price_including_tax,
                'created_at': row.created_at
            })

        return data, total

    @staticmethod
    def get_all_pos_data(
        db: Session,
        store_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all POS data for download (no pagination).

        Args:
            db: Database session
            store_name: Optional filter by store name

        Returns:
            List of all POS data items
        """
        query = POSRetrievalRepository._build_pos_data_query(db)

        # Apply store filter if provided
        if store_name:
            query = query.filter(BarcodeProduct.store_name.ilike(f"%{store_name}%"))

        # Order by created_at descending
        query = query.order_by(BarcodeProduct.created_at.desc())

        results = query.all()

        # Convert to list of dicts
        data = []
        for row in results:
            # Format general_note with promoter name and barcode count per page
            general_note = f"Promoter: {row.promoter_name} | Page {row.page_number}: {row.barcode_count} barcodes"
            data.append({
                'id': row.id,
                'date': row.date,
                'general_note': general_note,
                'store_name': row.store_name,
                'ykey': row.ykey,
                'product_name': row.product_name,
                'unit_of_measurement': row.unit_of_measurement,
                'quantity': row.quantity,
                'unit_price': row.unit_price,
                'taxes': row.taxes,
                'price_excluding_tax': row.price_excluding_tax,
                'price_including_tax': row.price_including_tax,
                'created_at': row.created_at
            })

        return data

    @staticmethod
    def get_pos_data_by_date_range(
        db: Session,
        start_date: date,
        end_date: date,
        store_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get POS data within a date range for download.
        Matches by created_at date (ignores time portion).

        Args:
            db: Database session
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            store_name: Optional filter by store name

        Returns:
            List of POS data items within the date range
        """
        query = POSRetrievalRepository._build_pos_data_query(db)

        # Filter by date range using created_at (cast to date for comparison)
        query = query.filter(
            and_(
                cast(BarcodeProduct.created_at, Date) >= start_date,
                cast(BarcodeProduct.created_at, Date) <= end_date
            )
        )

        # Apply store filter if provided
        if store_name:
            query = query.filter(BarcodeProduct.store_name.ilike(f"%{store_name}%"))

        # Order by created_at descending
        query = query.order_by(BarcodeProduct.created_at.desc())

        results = query.all()

        # Convert to list of dicts
        data = []
        for row in results:
            # Format general_note with promoter name and barcode count per page
            general_note = f"Promoter: {row.promoter_name} | Page {row.page_number}: {row.barcode_count} barcodes"
            data.append({
                'id': row.id,
                'date': row.date,
                'general_note': general_note,
                'store_name': row.store_name,
                'ykey': row.ykey,
                'product_name': row.product_name,
                'unit_of_measurement': row.unit_of_measurement,
                'quantity': row.quantity,
                'unit_price': row.unit_price,
                'taxes': row.taxes,
                'price_excluding_tax': row.price_excluding_tax,
                'price_including_tax': row.price_including_tax,
                'created_at': row.created_at
            })

        return data

    @staticmethod
    def get_available_stores(db: Session) -> List[str]:
        """Get list of all stores with POS data"""
        stores = db.query(BarcodeProduct.store_name)\
            .filter(BarcodeProduct.store_name.isnot(None))\
            .distinct()\
            .order_by(BarcodeProduct.store_name)\
            .all()

        return [s[0] for s in stores if s[0]]
