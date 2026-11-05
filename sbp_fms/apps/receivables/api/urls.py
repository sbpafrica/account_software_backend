from django.urls import path
from apps.receivables.api.public import ClientInvoiceListPublicApi
from apps.receivables.api.admin import (
    ClientListAdminApi, ClientInvoiceListAdminApi, AgingReportAdminApi
)

urlpatterns = [
    path('public/clients/<uuid:client_id>/invoices/', ClientInvoiceListPublicApi.as_view(), name='client-invoices-public'),
    path('admin/clients/', ClientListAdminApi.as_view(), name='client-list-admin'),
    path('admin/invoices/', ClientInvoiceListAdminApi.as_view(), name='client-invoice-list-admin'),
    path('admin/aging-report/', AgingReportAdminApi.as_view(), name='receivables-aging-report-admin'),
]
