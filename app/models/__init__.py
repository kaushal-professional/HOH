"""
Database models for the application.
"""

from app.core.database import Base
from app.models.shop import Shop
from app.models.product import Product, State, Store, StoreProduct, StateProduct
from app.models.article_code import ArticleCode, Promoter
from app.models.price_consolidated import PriceConsolidated
from app.models.price_pos import PricePos
from app.models.pos_entry import GeneralNote, Item, Barcode, BarcodeProduct

# from app.models.purchase import (
#     PurchaseOrder,
#     POItem,
#     POItemBox,
# )
# from app.models.purchase_approval import (
#     PurchaseApproval,
#     PurchaseApprovalItem,
#     PurchaseApprovalBox,
# )
# from app.models.item_catalog import (
#     CFPLItem,
#     CDPLItem,
# )

__all__ = [
    "Base",
    "Shop",
    "Product",
    "State",
    "Store",
    "StoreProduct",
    "StateProduct",
    "ArticleCode",
    "Promoter",
    "PriceConsolidated",
    "PricePos",
    "GeneralNote",
    "Item",
    "Barcode",
    "BarcodeProduct",
    # "PurchaseOrder",
    # "POItem",
    # "POItemBox",
    # "PurchaseApproval",
    # "PurchaseApprovalItem",
    # "PurchaseApprovalBox",
    # "CFPLItem",
    # "CDPLItem",
]

