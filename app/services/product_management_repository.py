"""
Repository layer for comprehensive product management operations.
Handles products with promoter assignments, pricing, and store assignments.
"""

from typing import List, Optional, Tuple, Dict
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.product import Product, Store, StoreProduct
from app.models.article_code import ArticleCode, Promoter
from app.models.price_consolidated import PriceConsolidated
from app.schemas.product_management import (
    ProductManagementCreate,
    ProductManagementUpdate,
    PromoterAssignmentCreate,
    PriceCreate,
    PriceUpdate,
)


class ProductManagementRepository:
    """Repository for comprehensive product management"""

    @staticmethod
    def create_product_with_assignments(
        db: Session,
        product_data: ProductManagementCreate
    ) -> Product:
        """
        Create a product with all assignments (promoters, prices, stores).

        Workflow:
        1. Create product
        2. Assign product to stores (store_products table)
        3. Find promoters for each store (via promoter table)
        4. Auto-create article codes for store-promoter combinations (if enabled)
        5. Create manual promoter assignments (if provided)
        6. Create price entries
        """
        # Check if product already exists
        existing = db.query(Product).filter(
            Product.product_id == product_data.product_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with ID {product_data.product_id} already exists"
            )

        # Create the product
        db_product = Product(
            product_id=product_data.product_id,
            product_type=product_data.product_type,
            product_description=product_data.product_description,
            is_active=product_data.is_active,
        )
        db.add(db_product)
        db.flush()

        # Track promoters from stores for auto-creation
        store_promoters = []

        # Create store assignments FIRST (this is the primary relationship)
        if product_data.store_ids:
            for store_id in product_data.store_ids:
                # Verify store exists
                store = db.query(Store).filter(Store.store_id == store_id).first()
                if not store:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Store with ID {store_id} not found"
                    )

                # Check if mapping already exists
                existing_mapping = db.query(StoreProduct).filter(
                    and_(
                        StoreProduct.store_id == store_id,
                        StoreProduct.product_id == product_data.product_id
                    )
                ).first()

                if not existing_mapping:
                    db_store_product = StoreProduct(
                        store_id=store_id,
                        product_id=product_data.product_id,
                        is_available=True
                    )
                    db.add(db_store_product)

                # Find promoters for this store
                # The promoter table links stores via point_of_sale field matching store_name
                promoters = db.query(Promoter).filter(
                    Promoter.point_of_sale.ilike(f"%{store.store_name}%")
                ).all()

                for promoter in promoters:
                    store_promoters.append({
                        "store_id": store_id,
                        "store_name": store.store_name,
                        "promoter": promoter.promoter
                    })

        # Auto-create article codes for store-promoter combinations
        if product_data.auto_create_article_codes and product_data.base_article_code:
            article_code_counter = product_data.base_article_code

            for sp in store_promoters:
                # Check if article code already exists
                existing_article = db.query(ArticleCode).filter(
                    ArticleCode.article_codes == article_code_counter
                ).first()

                if not existing_article:
                    db_article = ArticleCode(
                        products=product_data.product_description,
                        article_codes=article_code_counter,
                        promoter=sp["promoter"]
                    )
                    db.add(db_article)
                    article_code_counter += 1

        # Create manual promoter assignments (article codes)
        # These override or supplement the auto-created ones
        if product_data.promoter_assignments:
            for assignment in product_data.promoter_assignments:
                # Check if article code already exists
                existing_article = db.query(ArticleCode).filter(
                    ArticleCode.article_codes == assignment.article_code
                ).first()

                if existing_article:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Article code {assignment.article_code} already exists"
                    )

                db_article = ArticleCode(
                    products=product_data.product_description,
                    article_codes=assignment.article_code,
                    promoter=assignment.promoter
                )
                db.add(db_article)

        # Create price entries
        if product_data.prices:
            for price_info in product_data.prices:
                db_price = PriceConsolidated(
                    pricelist=price_info.pricelist,
                    product=product_data.product_description,
                    price=price_info.price,
                    gst=price_info.gst
                )
                db.add(db_price)

        db.commit()
        db.refresh(db_product)
        return db_product

    @staticmethod
    def get_product_with_all_data(db: Session, product_id: str) -> Optional[Dict]:
        """Get product with all related data (promoters, prices, stores)"""
        product = db.query(Product).filter(Product.product_id == product_id).first()

        if not product:
            return None

        # Get promoter assignments
        promoter_assignments = db.query(ArticleCode).filter(
            ArticleCode.products == product.product_description
        ).all()

        # Get prices
        prices = db.query(PriceConsolidated).filter(
            PriceConsolidated.product == product.product_description
        ).all()

        # Get store assignments with store details
        store_assignments = db.query(StoreProduct).options(
            joinedload(StoreProduct.store).joinedload(Store.state)
        ).filter(
            StoreProduct.product_id == product_id
        ).all()

        return {
            "product": product,
            "promoter_assignments": promoter_assignments,
            "prices": prices,
            "store_assignments": store_assignments
        }

    @staticmethod
    def get_all_products_with_data(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        product_type: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        promoter_filter: Optional[str] = None
    ) -> Tuple[List[Dict], int]:
        """Get all products with their related data"""
        query = db.query(Product)

        # Apply filters
        if product_type:
            query = query.filter(Product.product_type == product_type)
        if search:
            query = query.filter(
                or_(
                    Product.product_description.ilike(f"%{search}%"),
                    Product.product_id.ilike(f"%{search}%")
                )
            )
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)

        # Promoter filter requires join with article_codes
        if promoter_filter:
            query = query.join(
                ArticleCode,
                Product.product_description == ArticleCode.products
            ).filter(ArticleCode.promoter.ilike(f"%{promoter_filter}%"))

        total = query.count()

        products = query.order_by(
            Product.product_type,
            Product.product_description
        ).offset(skip).limit(limit).all()

        # Get related data for each product
        result = []
        for product in products:
            promoter_assignments = db.query(ArticleCode).filter(
                ArticleCode.products == product.product_description
            ).all()

            prices = db.query(PriceConsolidated).filter(
                PriceConsolidated.product == product.product_description
            ).all()

            store_assignments = db.query(StoreProduct).options(
                joinedload(StoreProduct.store).joinedload(Store.state)
            ).filter(
                StoreProduct.product_id == product.product_id
            ).all()

            result.append({
                "product": product,
                "promoter_assignments": promoter_assignments,
                "prices": prices,
                "store_assignments": store_assignments
            })

        return result, total

    @staticmethod
    def update_product(
        db: Session,
        product_id: str,
        update_data: ProductManagementUpdate
    ) -> Optional[Product]:
        """Update product basic information"""
        product = db.query(Product).filter(Product.product_id == product_id).first()

        if not product:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(product, field, value)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def delete_product(db: Session, product_id: str) -> bool:
        """Delete product (cascade deletes related data)"""
        product = db.query(Product).filter(Product.product_id == product_id).first()

        if not product:
            return False

        # Delete related price entries
        db.query(PriceConsolidated).filter(
            PriceConsolidated.product == product.product_description
        ).delete()

        # Delete related article codes
        db.query(ArticleCode).filter(
            ArticleCode.products == product.product_description
        ).delete()

        # Delete product (store_products will cascade due to FK)
        db.delete(product)
        db.commit()
        return True


class PromoterAssignmentRepository:
    """Repository for managing promoter assignments (article codes)"""

    @staticmethod
    def add_promoter_assignment(
        db: Session,
        product_description: str,
        assignment: PromoterAssignmentCreate
    ) -> ArticleCode:
        """Add a promoter assignment to a product"""
        # Check if article code already exists
        existing = db.query(ArticleCode).filter(
            ArticleCode.article_codes == assignment.article_code
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Article code {assignment.article_code} already exists"
            )

        db_article = ArticleCode(
            products=product_description,
            article_codes=assignment.article_code,
            promoter=assignment.promoter
        )
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        return db_article

    @staticmethod
    def update_promoter_assignment(
        db: Session,
        article_id: int,
        promoter: str
    ) -> Optional[ArticleCode]:
        """Update promoter assignment"""
        article = db.query(ArticleCode).filter(ArticleCode.id == article_id).first()

        if not article:
            return None

        article.promoter = promoter
        db.commit()
        db.refresh(article)
        return article

    @staticmethod
    def delete_promoter_assignment(db: Session, article_id: int) -> bool:
        """Delete promoter assignment"""
        article = db.query(ArticleCode).filter(ArticleCode.id == article_id).first()

        if not article:
            return False

        db.delete(article)
        db.commit()
        return True

    @staticmethod
    def get_assignments_by_product(
        db: Session,
        product_description: str
    ) -> List[ArticleCode]:
        """Get all promoter assignments for a product"""
        return db.query(ArticleCode).filter(
            ArticleCode.products == product_description
        ).all()


class PriceManagementRepository:
    """Repository for managing product prices"""

    @staticmethod
    def create_price(db: Session, price_data: PriceCreate) -> PriceConsolidated:
        """Create a price entry"""
        db_price = PriceConsolidated(**price_data.model_dump())
        db.add(db_price)
        db.commit()
        db.refresh(db_price)
        return db_price

    @staticmethod
    def get_price_by_id(db: Session, price_id: int) -> Optional[PriceConsolidated]:
        """Get price by ID"""
        return db.query(PriceConsolidated).filter(
            PriceConsolidated.id == price_id
        ).first()

    @staticmethod
    def get_prices_by_product(
        db: Session,
        product_name: str
    ) -> List[PriceConsolidated]:
        """Get all prices for a product"""
        return db.query(PriceConsolidated).filter(
            PriceConsolidated.product == product_name
        ).all()

    @staticmethod
    def get_all_prices(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        pricelist: Optional[str] = None,
        product: Optional[str] = None
    ) -> Tuple[List[PriceConsolidated], int]:
        """Get all prices with filters"""
        query = db.query(PriceConsolidated)

        if pricelist:
            query = query.filter(PriceConsolidated.pricelist.ilike(f"%{pricelist}%"))
        if product:
            query = query.filter(PriceConsolidated.product.ilike(f"%{product}%"))

        total = query.count()
        prices = query.order_by(
            PriceConsolidated.pricelist,
            PriceConsolidated.product
        ).offset(skip).limit(limit).all()

        return prices, total

    @staticmethod
    def update_price(
        db: Session,
        price_id: int,
        update_data: PriceUpdate
    ) -> Optional[PriceConsolidated]:
        """Update price"""
        price = PriceManagementRepository.get_price_by_id(db, price_id)

        if not price:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(price, field, value)

        db.commit()
        db.refresh(price)
        return price

    @staticmethod
    def delete_price(db: Session, price_id: int) -> bool:
        """Delete price"""
        price = PriceManagementRepository.get_price_by_id(db, price_id)

        if not price:
            return False

        db.delete(price)
        db.commit()
        return True

    @staticmethod
    def delete_prices_by_product(db: Session, product_name: str) -> int:
        """Delete all prices for a product"""
        count = db.query(PriceConsolidated).filter(
            PriceConsolidated.product == product_name
        ).delete()
        db.commit()
        return count
