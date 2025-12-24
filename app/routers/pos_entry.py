"""
POS Entry router for handling POS entry operations.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.models.pos_entry import GeneralNote, Item, Barcode, BarcodeProduct
from app.schemas.pos_entry import (
    POSEntryRequest,
    POSEntryResponse,
    GeneralNoteResponse,
    ItemResponse,
    BarcodeResponse,
    BarcodeProductResponse
)

router = APIRouter(prefix="/pos-entries", tags=["POS Entries"])


@router.post("", response_model=POSEntryResponse, status_code=status.HTTP_201_CREATED)
def create_pos_entry(
    pos_entry: POSEntryRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new POS entry with items and scanned barcodes.

    This endpoint accepts the complete POS entry payload from the frontend
    and saves it to the database across multiple related tables:
    - general_notes
    - items
    - barcodes
    - barcode_products
    """
    try:
        # Parse date from DD-MM-YYYY format
        note_date = datetime.strptime(pos_entry.general_note.date, "%d-%m-%Y").date()

        # 1. Create General Note
        general_note = GeneralNote(
            note_date=note_date,
            promoter_name=pos_entry.general_note.promoter_name,
            note=pos_entry.general_note.note_text,
            store_name=pos_entry.store_name
        )
        db.add(general_note)
        db.commit()  # Commit to get the ID
        db.refresh(general_note)

        # 2. Create Items
        items_to_add = []
        for item_data in pos_entry.items:
            item = Item(
                general_note_id=general_note.id,
                ykey=item_data.ykey,
                product=item_data.product,
                quantity=item_data.quantity,
                price=item_data.price,
                unit=item_data.unit,
                discount=item_data.discount,
                store_name=pos_entry.store_name
            )
            items_to_add.append(item)

        db.add_all(items_to_add)
        db.commit()

        # Refresh all items
        for item in items_to_add:
            db.refresh(item)

        # 3. Create Barcodes and Barcode Products
        all_barcode_responses = []
        total_products_scanned = 0

        for page_data in pos_entry.general_note.barcode_scanned_pages:
            # Create barcode page
            barcode = Barcode(
                general_note_id=general_note.id,
                page_number=page_data.page_number,
                count=page_data.total_count
            )
            db.add(barcode)
            db.commit()  # Commit to get the ID
            db.refresh(barcode)

            # Create barcode products for this page
            products_to_add = []
            for product_data in page_data.products:
                barcode_product = BarcodeProduct(
                    barcode_id=barcode.id,
                    barcode=product_data.barcode,
                    product=product_data.product,
                    price=product_data.price,
                    article_code=product_data.article_code,
                    weight_code=product_data.weight_code,
                    barcode_format=product_data.barcode_format,
                    store_name=product_data.store_name,
                    pricelist=product_data.pricelist,
                    weight=product_data.weight,
                    gst=product_data.gst,
                    price_with_gst=product_data.price_with_gst
                )
                products_to_add.append(barcode_product)
                total_products_scanned += 1

            db.add_all(products_to_add)
            db.commit()

            # Refresh all products
            product_responses = []
            for product in products_to_add:
                db.refresh(product)
                product_responses.append(
                    BarcodeProductResponse(
                        id=product.id,
                        barcode=product.barcode,
                        product=product.product,
                        price=product.price,
                        article_code=product.article_code,
                        weight_code=product.weight_code,
                        barcode_format=product.barcode_format,
                        store_name=product.store_name,
                        pricelist=product.pricelist,
                        weight=product.weight,
                        gst=product.gst,
                        price_with_gst=product.price_with_gst,
                        created_at=product.created_at
                    )
                )

            # Build barcode response with products
            all_barcode_responses.append(
                BarcodeResponse(
                    id=barcode.id,
                    page_number=barcode.page_number,
                    count=barcode.count,
                    products=product_responses,
                    created_at=barcode.created_at
                )
            )

        # 4. Build and return response
        return POSEntryResponse(
            general_note=GeneralNoteResponse(
                id=general_note.id,
                note_date=general_note.note_date,
                promoter_name=general_note.promoter_name,
                note=general_note.note,
                store_name=general_note.store_name,
                created_at=general_note.created_at,
                updated_at=general_note.updated_at
            ),
            items=[
                ItemResponse(
                    id=item.id,
                    ykey=item.ykey,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.price,
                    unit=item.unit,
                    discount=item.discount,
                    store_name=item.store_name,
                    created_at=item.created_at
                )
                for item in items_to_add
            ],
            barcodes=all_barcode_responses,
            total_items=len(items_to_add),
            total_barcode_pages=len(all_barcode_responses),
            total_products_scanned=total_products_scanned
        )

    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Expected DD-MM-YYYY: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating POS entry: {str(e)}"
        )


@router.get("/{general_note_id}", response_model=POSEntryResponse)
def get_pos_entry(
    general_note_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a POS entry by general_note_id with all related items and barcodes.
    """
    general_note = db.query(GeneralNote).filter(GeneralNote.id == general_note_id).first()

    if not general_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POS entry with ID {general_note_id} not found"
        )

    # Get all related data
    items = db.query(Item).filter(Item.general_note_id == general_note_id).all()
    barcodes = db.query(Barcode).filter(Barcode.general_note_id == general_note_id).all()

    # Get products for each barcode
    total_products = 0
    barcode_responses = []
    for barcode in barcodes:
        products = db.query(BarcodeProduct).filter(BarcodeProduct.barcode_id == barcode.id).all()
        total_products += len(products)

        barcode_responses.append(
            BarcodeResponse(
                id=barcode.id,
                page_number=barcode.page_number,
                count=barcode.count,
                products=[
                    BarcodeProductResponse(
                        id=p.id,
                        barcode=p.barcode,
                        product=p.product,
                        price=p.price,
                        article_code=p.article_code,
                        weight_code=p.weight_code,
                        barcode_format=p.barcode_format,
                        store_name=p.store_name,
                        pricelist=p.pricelist,
                        weight=p.weight,
                        gst=p.gst,
                        price_with_gst=p.price_with_gst,
                        created_at=p.created_at
                    )
                    for p in products
                ],
                created_at=barcode.created_at
            )
        )

    return POSEntryResponse(
        general_note=GeneralNoteResponse(
            id=general_note.id,
            note_date=general_note.note_date,
            promoter_name=general_note.promoter_name,
            note=general_note.note,
            store_name=general_note.store_name,
            created_at=general_note.created_at,
            updated_at=general_note.updated_at
        ),
        items=[
            ItemResponse(
                id=item.id,
                ykey=item.ykey,
                product=item.product,
                quantity=item.quantity,
                price=item.price,
                unit=item.unit,
                discount=item.discount,
                store_name=item.store_name,
                created_at=item.created_at
            )
            for item in items
        ],
        barcodes=barcode_responses,
        total_items=len(items),
        total_barcode_pages=len(barcodes),
        total_products_scanned=total_products
    )
