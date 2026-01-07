"""
API routers for the application.
"""

from fastapi import APIRouter
from app.routers import shop, product, store_product_flat, article_code, pos_entry, stock_take, product_management, price_pos, price_consolidated, login
# from app.routers import purchase, purchase_approval, item_catalog, pdf_extraction, whatsapp, auth, inward, ims_auth

api_router = APIRouter()

# Include routers
api_router.include_router(login.router)  # Admin Login & Authentication
api_router.include_router(shop.router)
api_router.include_router(product.router)  # Product & Store mapping system
api_router.include_router(store_product_flat.router)  # Store Product Flat table
api_router.include_router(article_code.router)  # Article codes & Promoters
api_router.include_router(price_pos.router)  # Price POS (Point of Sale) mapping
api_router.include_router(price_consolidated.router)  # Price Consolidated (Product Pricing)
api_router.include_router(pos_entry.router)  # POS Entry system
api_router.include_router(stock_take.router)  # Stock Take Management system
api_router.include_router(product_management.router)  # Comprehensive Product Management (Unified)
# api_router.include_router(ims_auth.router)  # Authentication system
# api_router.include_router(purchase.router)
# api_router.include_router(purchase_approval.router)
# api_router.include_router(item_catalog.router)
# api_router.include_router(pdf_extraction.router)
# api_router.include_router(whatsapp.router)
# api_router.include_router(auth.router)
# api_router.include_router(inward.router)

__all__ = ["api_router", "login", "shop", "product", "store_product_flat", "article_code", "price_pos", "price_consolidated", "pos_entry", "stock_take", "product_management"]

