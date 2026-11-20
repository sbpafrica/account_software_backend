from django.urls import path
from apps.receivables.api.public import ClientInvoiceListPublicApi
from apps.receivables.api.admin import (
    ClientListAdminApi, ClientDetailAdminApi,
    ClientInvoiceListAdminApi, ClientInvoiceDetailAdminApi,
    ClientInvoiceIssueAdminApi,
    PaymentReceiptListAdminApi, PaymentReceiptDetailAdminApi,
    CustomerStatementAdminApi,
    AgingReportAdminApi,
    ClientInvoiceTemplateListAdminApi, ClientInvoiceTemplateDetailAdminApi,
    InvoiceTemplatePresetsAdminApi, InvoiceBuilderPreviewAdminApi,
    ClientInvoiceRenderAdminApi
)

from apps.receivables.api.paystack_views import (
    InvoicePaystackInitializeApi,
    InvoicePaystackVerifyApi,
)

urlpatterns = [
    # Public Client Facing
    path('public/clients/<uuid:client_id>/invoices/', ClientInvoiceListPublicApi.as_view(), name='client-invoices-public'),

    # Paystack Invoice Checkout & Payment Verification (Idempotent & Atomic)
    path('invoices/<uuid:invoice_id>/paystack/initialize/', InvoicePaystackInitializeApi.as_view(), name='invoice-paystack-initialize'),
    path('invoices/paystack/verify/', InvoicePaystackVerifyApi.as_view(), name='invoice-paystack-verify'),

    # Admin / Clients & Statements
    path('admin/clients/', ClientListAdminApi.as_view(), name='client-list-admin'),
    path('admin/clients/<uuid:client_id>/', ClientDetailAdminApi.as_view(), name='client-detail-admin'),
    path('admin/clients/<uuid:client_id>/statement/', CustomerStatementAdminApi.as_view(), name='customer-statement-admin'),

    # Admin / Invoices
    path('admin/invoices/', ClientInvoiceListAdminApi.as_view(), name='client-invoice-list-admin'),
    path('admin/invoices/<uuid:invoice_id>/', ClientInvoiceDetailAdminApi.as_view(), name='client-invoice-detail-admin'),
    path('admin/invoices/<uuid:invoice_id>/issue/', ClientInvoiceIssueAdminApi.as_view(), name='client-invoice-issue-admin'),
    path('admin/invoices/<uuid:invoice_id>/render/', ClientInvoiceRenderAdminApi.as_view(), name='client-invoice-render-admin'),

    # Admin / Invoice Builder & Field Presets
    path('admin/invoice-templates/', ClientInvoiceTemplateListAdminApi.as_view(), name='invoice-template-list-admin'),
    path('admin/invoice-templates/<uuid:template_id>/', ClientInvoiceTemplateDetailAdminApi.as_view(), name='invoice-template-detail-admin'),
    path('admin/invoice-templates/presets/', InvoiceTemplatePresetsAdminApi.as_view(), name='invoice-template-presets-admin'),
    path('admin/invoice-templates/preview/', InvoiceBuilderPreviewAdminApi.as_view(), name='invoice-builder-preview-admin'),

    # Admin / Payment Receipts
    path('admin/receipts/', PaymentReceiptListAdminApi.as_view(), name='payment-receipt-list-admin'),
    path('admin/receipts/<uuid:receipt_id>/', PaymentReceiptDetailAdminApi.as_view(), name='payment-receipt-detail-admin'),

    # Admin / Debtor Aging Report
    path('admin/aging-report/', AgingReportAdminApi.as_view(), name='receivables-aging-report-admin'),
]

