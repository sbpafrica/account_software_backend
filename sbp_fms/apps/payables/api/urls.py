from django.urls import path
from apps.payables.api.public import SupplierInvoiceStatusPublicApi
from apps.payables.api.admin import (
    SupplierListAdminApi, SupplierDetailAdminApi,
    PurchaseOrderListAdminApi, PurchaseOrderDetailAdminApi,
    GoodsReceivedNoteListAdminApi, GoodsReceivedNoteDetailAdminApi,
    SupplierInvoiceListAdminApi, SupplierInvoiceDetailAdminApi,
    ThreeWayMatchRunAdminApi
)

urlpatterns = [
    # Public Vendor Facing
    path('public/invoices/<uuid:invoice_id>/status/', SupplierInvoiceStatusPublicApi.as_view(), name='supplier-invoice-status-public'),

    # Admin / Suppliers
    path('admin/suppliers/', SupplierListAdminApi.as_view(), name='supplier-list-admin'),
    path('admin/suppliers/<uuid:supplier_id>/', SupplierDetailAdminApi.as_view(), name='supplier-detail-admin'),

    # Admin / Purchase Orders
    path('admin/purchase-orders/', PurchaseOrderListAdminApi.as_view(), name='purchase-order-list-admin'),
    path('admin/purchase-orders/<uuid:po_id>/', PurchaseOrderDetailAdminApi.as_view(), name='purchase-order-detail-admin'),

    # Admin / Goods Received Notes
    path('admin/goods-received-notes/', GoodsReceivedNoteListAdminApi.as_view(), name='grn-list-admin'),
    path('admin/goods-received-notes/<uuid:grn_id>/', GoodsReceivedNoteDetailAdminApi.as_view(), name='grn-detail-admin'),

    # Admin / Supplier Invoices & 3-Way Match
    path('admin/invoices/', SupplierInvoiceListAdminApi.as_view(), name='supplier-invoice-list-admin'),
    path('admin/invoices/<uuid:invoice_id>/', SupplierInvoiceDetailAdminApi.as_view(), name='supplier-invoice-detail-admin'),
    path('admin/invoices/<uuid:invoice_id>/match/', ThreeWayMatchRunAdminApi.as_view(), name='supplier-invoice-match-admin'),
]
