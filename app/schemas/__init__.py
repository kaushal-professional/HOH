"""
Schemas for the application.

This module exports all Pydantic models and schemas used for request/response validation.
"""

from app.schemas.shop import (
    ShopBase,
    ShopCreate,
    ShopUpdate,
    ShopOut,
    ShopLogin,
    ShopLoginResponse,
)

from app.schemas.product import (
    # Product schemas
    ProductBase,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    # State schemas
    StateBase,
    StateCreate,
    StateUpdate,
    StateResponse,
    # Store schemas
    StoreBase,
    StoreCreate,
    StoreUpdate,
    StoreResponse,
    StoreDetailResponse,
    # Store-Product mapping schemas
    StoreProductBase,
    StoreProductCreate,
    StoreProductBulkCreate,
    StoreProductUpdate,
    StoreProductResponse,
    StoreProductDetailResponse,
    # State-Product mapping schemas
    StateProductBase,
    StateProductCreate,
    StateProductBulkCreate,
    StateProductResponse,
    # User query schemas
    ProductAvailabilityCheck,
    UserProductsResponse,
    ProductTypeResponse,
    # Utility schemas
    PaginationParams,
    ProductFilterParams,
    SuccessResponse,
    ErrorResponse,
    BulkOperationResponse,
)

# from app.schemas.purchase import (
#     # Shared value objects
#     Currency,
#     PurchaseOrderInfo,
#     Party,
#     FinancialSummary,
#
#     # Purchase Order schemas
#     PurchaseOrderCreate,
#     PurchaseOrderUpdate,
#     PurchaseOrderOut,
#
#     # Item schemas
#     ItemCreate,
#     ItemUpdate,
#     ItemOut,
#
#     # Box schemas
#     BoxCreate,
#     BoxUpdate,
#     BoxOut,
#
#     # Utility schemas
#     DeleteRequest,
# )
#
# from app.schemas.purchase_approval import (
#     # Purchase Approval schemas
#     PurchaseApprovalCreate,
#     PurchaseApprovalUpdate,
#     PurchaseApprovalOut,
#     PurchaseApprovalWithItemsOut,
#     PurchaseApprovalItemOut,
#     PurchaseApprovalBoxOut,
#     # Nested schemas
#     TransporterInformation,
#     CustomerInformation,
#     ItemSchema,
#     BoxSchema,
# )
#
# from app.schemas.item_catalog import (
#     # Item Catalog schemas
#     ItemCatalogBase,
#     ItemDetailsResponse,
#     DropdownValuesResponse,
#     CascadingDropdownRequest,
#     AutoFillRequest,
#     GlobalSearchRequest,
#     GlobalSearchResponse,
# )
#
# from app.schemas.whatsapp import (
#     # WhatsApp schemas
#     WhatsAppWebhookRequest,
#     WhatsAppMessageResponse,
#     PDFProcessingRequest,
#     PDFProcessingResponse,
# )

__all__ = [
    # Shop schemas
    "ShopBase",
    "ShopCreate",
    "ShopUpdate",
    "ShopOut",
    "ShopLogin",
    "ShopLoginResponse",

    # # Shared value objects
    # "Currency",
    # "PurchaseOrderInfo",
    # "Party",
    # "FinancialSummary",
    #
    # # Purchase Order schemas
    # "PurchaseOrderCreate",
    # "PurchaseOrderUpdate",
    # "PurchaseOrderOut",
    #
    # # Item schemas
    # "ItemCreate",
    # "ItemUpdate",
    # "ItemOut",
    #
    # # Box schemas
    # "BoxCreate",
    # "BoxUpdate",
    # "BoxOut",
    #
    # # Utility schemas
    # "DeleteRequest",
    #
    # # Purchase Approval schemas
    # "PurchaseApprovalCreate",
    # "PurchaseApprovalUpdate",
    # "PurchaseApprovalOut",
    # "PurchaseApprovalWithItemsOut",
    # "PurchaseApprovalItemOut",
    # "PurchaseApprovalBoxOut",
    # "TransporterInformation",
    # "CustomerInformation",
    # "ItemSchema",
    # "BoxSchema",
    #
    # # Item Catalog schemas
    # "ItemCatalogBase",
    # "ItemDetailsResponse",
    # "DropdownValuesResponse",
    # "CascadingDropdownRequest",
    # "AutoFillRequest",
    # "GlobalSearchRequest",
    # "GlobalSearchResponse",
    #
    # # WhatsApp schemas
    # "WhatsAppWebhookRequest",
    # "WhatsAppMessageResponse",
    # "PDFProcessingRequest",
    # "PDFProcessingResponse",
]

