from django.urls import path
from apps.payables.api.public import SupplierInvoiceStatusPublicApi
from apps.payables.api.admin import (
    SupplierListAdminApi, SupplierInvoiceListAdminApi,
    SupplierInvoiceDetailAdminApi, ThreeWayMatchRunAdminApi
)

urlpatterns = [
    path('public/invoices/<uuid:invoice_id>/status/', SupplierInvoiceStatusPublicApi.as_view(), name='supplier-invoice-status-public'),
    path('admin/suppliers/', SupplierListAdminApi.as_view(), name='supplier-list-admin'),
    path('admin/invoices/', SupplierInvoiceListAdminApi.as_view(), name='supplier-invoice-list-admin'),
    path('admin/invoices/<uuid:invoice_id>/', SupplierInvoiceDetailAdminApi.as_view(), name='supplier-invoice-detail-admin'),
    path('admin/invoices/<uuid:invoice_id>/match/', ThreeWayMatchRunAdminApi.as_view(), name='supplier-invoice-match-admin'),
]
