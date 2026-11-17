from django.contrib import admin
from apps.payables.models import (
    Supplier, PurchaseOrder, POLine,
    GoodsReceivedNote, GRNLine,
    SupplierInvoice, InvoiceLine,
    PaymentVoucher, VoucherLine,
    ExpenseClaim, ExpenseClaimLine
)


class POLineInline(admin.TabularInline):
    model = POLine
    extra = 1


class GRNLineInline(admin.TabularInline):
    model = GRNLine
    extra = 1


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


class VoucherLineInline(admin.TabularInline):
    model = VoucherLine
    extra = 1


class ExpenseClaimLineInline(admin.TabularInline):
    model = ExpenseClaimLine
    extra = 1


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_id', 'country_code', 'category', 'is_active', 'created_at')
    list_filter = ('country_code', 'is_active', 'category')
    search_fields = ('name', 'tax_id', 'email')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'total_approved_amount', 'is_approved', 'created_at')
    list_filter = ('is_approved',)
    search_fields = ('po_number', 'supplier__name')
    inlines = [POLineInline]


@admin.register(GoodsReceivedNote)
class GoodsReceivedNoteAdmin(admin.ModelAdmin):
    list_display = ('grn_number', 'po', 'received_date', 'created_at')
    search_fields = ('grn_number', 'po__po_number')
    inlines = [GRNLineInline]


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'supplier', 'bill_date', 'due_date', 'gross_amount', 'net_payable_amount', 'match_status')
    list_filter = ('match_status',)
    search_fields = ('invoice_number', 'supplier__name')
    inlines = [InvoiceLineInline]


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ('voucher_number', 'voucher_date', 'payee_name', 'payee_type', 'gross_amount', 'net_amount', 'status')
    list_filter = ('status', 'payee_type')
    search_fields = ('voucher_number', 'payee_name')
    inlines = [VoucherLineInline]


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_number', 'claim_date', 'employee', 'claim_type', 'total_expenses', 'net_payable_to_employee', 'status', 'country_code')
    list_filter = ('status', 'claim_type', 'country_code')
    search_fields = ('claim_number', 'employee__email')
    inlines = [ExpenseClaimLineInline]
