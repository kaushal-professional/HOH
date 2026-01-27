"""
POS Entry models for database operations.
"""

from sqlalchemy import Column, Integer, String, Text, Date, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class GeneralNote(Base):
    """
    General Notes table model.

    Table: general_notes
    Stores main POS entry information.
    """
    __tablename__ = "general_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("uuid_generate_v4()"))
    note_date = Column(Date, nullable=False)
    promoter_name = Column(Text, nullable=False)
    note = Column(Text)
    store_name = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    items = relationship("Item", back_populates="general_note", cascade="all, delete-orphan")
    barcodes = relationship("Barcode", back_populates="general_note", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GeneralNote(id={self.id}, promoter_name='{self.promoter_name}', note_date={self.note_date})>"


class Item(Base):
    """
    Items table model.

    Table: items
    Stores summary items for each POS entry.
    """
    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("uuid_generate_v4()"))
    general_note_id = Column(UUID(as_uuid=True), ForeignKey('general_notes.id', ondelete='CASCADE'), nullable=False)
    ykey = Column(Text, nullable=False)
    product = Column(Text, nullable=False)
    quantity = Column(Numeric(12, 3), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    unit = Column(Text, nullable=False)
    discount = Column(Numeric(12, 2), nullable=False)
    store_name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    general_note = relationship("GeneralNote", back_populates="items")

    def __repr__(self):
        return f"<Item(id={self.id}, product='{self.product}', quantity={self.quantity})>"


class Barcode(Base):
    """
    Barcodes table model.

    Table: barcodes
    Stores barcode page information.
    """
    __tablename__ = "barcodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("uuid_generate_v4()"))
    general_note_id = Column(UUID(as_uuid=True), ForeignKey('general_notes.id', ondelete='CASCADE'), nullable=False)
    page_number = Column(Integer, nullable=False)
    count = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    general_note = relationship("GeneralNote", back_populates="barcodes")
    barcode_products = relationship("BarcodeProduct", back_populates="barcode_page", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Barcode(id={self.id}, page_number={self.page_number}, count={self.count})>"


class BarcodeProduct(Base):
    """
    Barcode Products table model.

    Table: barcode_products
    Stores individual scanned products for each barcode page.
    """
    __tablename__ = "barcode_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("uuid_generate_v4()"))
    barcode_id = Column(UUID(as_uuid=True), ForeignKey('barcodes.id', ondelete='CASCADE'), nullable=False)
    barcode = Column(Text, nullable=False)
    product = Column(Text, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    article_code = Column(Integer)
    weight_code = Column(Text)
    barcode_format = Column(Text)
    store_name = Column(Text)
    pricelist = Column(Text)
    weight = Column(Numeric(12, 3))
    gst = Column(Numeric(12, 2))
    price_with_gst = Column(Numeric(12, 2))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships (renamed to avoid collision with 'barcode' column)
    barcode_page = relationship("Barcode", back_populates="barcode_products")

    def __repr__(self):
        return f"<BarcodeProduct(id={self.id}, barcode='{self.barcode}', product='{self.product}')>"
