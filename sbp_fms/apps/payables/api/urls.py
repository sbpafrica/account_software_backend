from django.urls import path
from apps.payables.api.public import SupplierInvoiceStatusPublicApi
from apps.payables.api.admin import (
    SupplierListAdminApi, SupplierDetailAdminApi,
    PurchaseOrderListAdminApi, PurchaseOrderDetailAdminApi,
    GoodsReceivedNoteListAdminApi, GoodsReceivedNoteDetailAdminApi,
    SupplierInvoiceListAdminApi, SupplierInvoiceDetailAdminApi,
    ThreeWayMatchRunAdminApi,
    PaymentVoucherListAdminApi, PaymentVoucherDetailAdminApi,
    PaymentVoucherSubmitAdminApi, PaymentVoucherReviewAdminApi,
    PaymentVoucherApproveAdminApi, PaymentVoucherRejectAdminApi,
    PaymentVoucherMarkPaidAdminApi, APAgingReportAdminApi,
    SupplierStatementAdminApi,
    ExpenseClaimListCreateAdminApi, ExpenseClaimDetailAdminApi,
    ExpenseClaimSubmitAdminApi, ExpenseClaimApproveAdminApi,
    ExpenseClaimRejectAdminApi, ExpenseClaimSettleAdminApi
)

urlpatterns = [
    # Public Vendor Facing
    path('public/invoices/<uuid:invoice_id>/status/', SupplierInvoiceStatusPublicApi.as_view(), name='supplier-invoice-status-public'),

    # Admin / Suppliers
    path('admin/suppliers/', SupplierListAdminApi.as_view(), name='supplier-list-admin'),
    path('admin/suppliers/<uuid:supplier_id>/', SupplierDetailAdminApi.as_view(), name='supplier-detail-admin'),
    path('admin/suppliers/<uuid:supplier_id>/statement/', SupplierStatementAdminApi.as_view(), name='supplier-statement-admin'),

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

    # Admin / Payment Vouchers
    path('admin/vouchers/', PaymentVoucherListAdminApi.as_view(), name='payment-voucher-list-admin'),
    path('admin/vouchers/<uuid:voucher_id>/', PaymentVoucherDetailAdminApi.as_view(), name='payment-voucher-detail-admin'),
    path('admin/vouchers/<uuid:voucher_id>/submit/', PaymentVoucherSubmitAdminApi.as_view(), name='payment-voucher-submit-admin'),
    path('admin/vouchers/<uuid:voucher_id>/review/', PaymentVoucherReviewAdminApi.as_view(), name='payment-voucher-review-admin'),
    path('admin/vouchers/<uuid:voucher_id>/approve/', PaymentVoucherApproveAdminApi.as_view(), name='payment-voucher-approve-admin'),
    path('admin/vouchers/<uuid:voucher_id>/reject/', PaymentVoucherRejectAdminApi.as_view(), name='payment-voucher-reject-admin'),
    path('admin/vouchers/<uuid:voucher_id>/mark-paid/', PaymentVoucherMarkPaidAdminApi.as_view(), name='payment-voucher-mark-paid-admin'),

    # Admin / AP Aging Report
    path('admin/aging-report/', APAgingReportAdminApi.as_view(), name='payables-aging-report-admin'),

    # Admin / Employee Expense Claims & Advance Retirement
    path('admin/expense-claims/', ExpenseClaimListCreateAdminApi.as_view(), name='expense-claim-list-create-admin'),
    path('admin/expense-claims/<uuid:claim_id>/', ExpenseClaimDetailAdminApi.as_view(), name='expense-claim-detail-admin'),
    path('admin/expense-claims/<uuid:claim_id>/submit/', ExpenseClaimSubmitAdminApi.as_view(), name='expense-claim-submit-admin'),
    path('admin/expense-claims/<uuid:claim_id>/approve/', ExpenseClaimApproveAdminApi.as_view(), name='expense-claim-approve-admin'),
    path('admin/expense-claims/<uuid:claim_id>/reject/', ExpenseClaimRejectAdminApi.as_view(), name='expense-claim-reject-admin'),
    path('admin/expense-claims/<uuid:claim_id>/settle/', ExpenseClaimSettleAdminApi.as_view(), name='expense-claim-settle-admin'),
]

