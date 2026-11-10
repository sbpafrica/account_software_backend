from django.urls import path
from apps.receivables.api.public import ClientInvoiceListPublicApi
from apps.receivables.api.admin import (
    ClientListAdminApi, ClientDetailAdminApi,
    ClientInvoiceListAdminApi, ClientInvoiceDetailAdminApi,
    AgingReportAdminApi
)

urlpatterns = [
    # Public Client Facing
    path('public/clients/<uuid:client_id>/invoices/', ClientInvoiceListPublicApi.as_view(), name='client-invoices-public'),

    # Admin / Finance Operations
    path('admin/clients/', ClientListAdminApi.as_view(), name='client-list-admin'),
    path('admin/clients/<uuid:client_id>/', ClientDetailAdminApi.as_view(), name='client-detail-admin'),
    path('admin/invoices/', ClientInvoiceListAdminApi.as_view(), name='client-invoice-list-admin'),
    path('admin/invoices/<uuid:invoice_id>/', ClientInvoiceDetailAdminApi.as_view(), name='client-invoice-detail-admin'),
    path('admin/aging-report/', AgingReportAdminApi.as_view(), name='receivables-aging-report-admin'),
]
