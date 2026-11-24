from django.contrib import admin
from apps.invoicing.models import (
    InvoiceCategory,
    InvoiceTemplate,
    BillableItem,
    Invoice,
    InvoiceLine,
    InvoiceTaxLine,
    RecurringSchedule,
    InvoiceDeliveryLog,
)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ['description', 'quantity', 'unit_of_measurement', 'unit_price', 'tax_code', 'line_total', 'custom_fields']


class InvoiceTaxLineInline(admin.TabularInline):
    model = InvoiceTaxLine
    extra = 0
    readonly_fields = ['tax_type', 'rate', 'base_amount', 'tax_amount']


@admin.register(InvoiceCategory)
class InvoiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'income_account', 'is_system', 'is_active', 'created_at']
    list_filter = ['is_system', 'is_active']
    search_fields = ['name', 'code', 'description']


@admin.register(InvoiceTemplate)
class InvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_name', 'preset_code', 'client', 'layout_style', 'is_default', 'is_active']
    list_filter = ['layout_style', 'is_default', 'is_active']
    search_fields = ['template_name', 'client__name', 'preset_code']


@admin.register(BillableItem)
class BillableItemAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'default_unit_price', 'default_unit', 'default_tax_code', 'is_active']
    list_filter = ['category', 'default_tax_code', 'is_active']
    search_fields = ['code', 'name', 'description']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number',
        'invoice_type',
        'client',
        'category',
        'issue_date',
        'due_date',
        'total_amount',
        'amount_paid',
        'status',
        'currency',
    ]
    list_filter = ['status', 'invoice_type', 'currency', 'category', 'issue_date']
    search_fields = ['invoice_number', 'reference_number', 'description', 'client__name']
    inlines = [InvoiceLineInline, InvoiceTaxLineInline]
    readonly_fields = ['subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'balance_due', 'journal_entry']


@admin.register(RecurringSchedule)
class RecurringScheduleAdmin(admin.ModelAdmin):
    list_display = ['schedule_name', 'client', 'category', 'frequency', 'next_run_date', 'status', 'auto_issue']
    list_filter = ['status', 'frequency', 'auto_issue']
    search_fields = ['schedule_name', 'client__name']


@admin.register(InvoiceDeliveryLog)
class InvoiceDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'delivery_channel', 'recipient_email', 'sent_at', 'is_success']
    list_filter = ['delivery_channel', 'is_success']
    search_fields = ['invoice__invoice_number', 'recipient_email']
