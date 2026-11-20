from django.contrib import admin
from apps.receivables.models import (
    Client, ClientInvoice, ClientInvoiceLine, PaymentReceipt, ReceiptAllocation,
    ClientInvoiceTemplate
)


class ClientInvoiceLineInline(admin.TabularInline):
    model = ClientInvoiceLine
    extra = 1


class ReceiptAllocationInline(admin.TabularInline):
    model = ReceiptAllocation
    extra = 1


@admin.register(ClientInvoiceTemplate)
class ClientInvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'client', 'layout_style', 'primary_color', 'is_default', 'is_active', 'created_at')
    list_filter = ('layout_style', 'is_default', 'is_active')
    search_fields = ('template_name', 'client__name', 'invoice_title')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'country_code', 'category', 'tax_id', 'is_active', 'created_at')
    list_filter = ('country_code', 'is_active', 'category')
    search_fields = ('name', 'code', 'tax_id', 'email')


@admin.register(ClientInvoice)
class ClientInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'template', 'issue_date', 'due_date', 'total_amount', 'amount_paid', 'status')
    list_filter = ('status', 'template')
    search_fields = ('invoice_number', 'client__name')
    inlines = [ClientInvoiceLineInline]


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'client', 'receipt_date', 'amount_received', 'payment_method', 'status')
    list_filter = ('status', 'payment_method')
    search_fields = ('receipt_number', 'client__name', 'reference_number')
    inlines = [ReceiptAllocationInline]
