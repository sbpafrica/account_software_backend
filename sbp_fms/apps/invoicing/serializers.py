from rest_framework import serializers
from decimal import Decimal
from apps.invoicing.models import (
    InvoiceCategory,
    InvoiceTemplate,
    BillableItem,
    Invoice,
    InvoiceLine,
    InvoiceTaxLine,
    RecurringSchedule,
    InvoiceType,
    InvoiceStatus,
    InvoiceLayoutStyle,
    RecurringFrequency,
    RecurringScheduleStatus,
)
from apps.receivables.models import Client
from apps.ledger.models import Account


class InvoiceCategorySerializer(serializers.ModelSerializer):
    income_account_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    income_account_code = serializers.CharField(source='income_account.code', read_only=True, default=None)
    income_account_name = serializers.CharField(source='income_account.name', read_only=True, default=None)

    class Meta:
        model = InvoiceCategory
        fields = [
            'id',
            'name',
            'code',
            'description',
            'income_account_id',
            'income_account_code',
            'income_account_name',
            'is_system',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'is_system', 'created_at', 'updated_at']


class InvoiceTemplateSerializer(serializers.ModelSerializer):
    client_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    client_name = serializers.CharField(source='client.name', read_only=True, default=None)

    class Meta:
        model = InvoiceTemplate
        fields = [
            'id',
            'template_name',
            'preset_code',
            'client_id',
            'client_name',
            'layout_style',
            'primary_color',
            'secondary_color',
            'accent_color',
            'logo_url',
            'show_logo',
            'font_family',
            'invoice_title',
            'show_tax_breakdown',
            'show_bank_details',
            'show_due_date_badge',
            'show_discount',
            'show_unit_of_measure',
            'default_notes',
            'default_terms',
            'footer_text',
            'header_custom_fields',
            'line_custom_fields',
            'is_default',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BillableItemSerializer(serializers.ModelSerializer):
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_code = serializers.CharField(source='category.code', read_only=True, default=None)
    income_account_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    income_account_code = serializers.CharField(source='income_account.code', read_only=True, default=None)

    class Meta:
        model = BillableItem
        fields = [
            'id',
            'code',
            'name',
            'category_id',
            'category_name',
            'category_code',
            'description',
            'default_unit',
            'default_unit_price',
            'default_tax_code',
            'default_tax_rate',
            'income_account_id',
            'income_account_code',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InvoiceLineSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True, default=None)
    item_name = serializers.CharField(source='item.name', read_only=True, default=None)

    class Meta:
        model = InvoiceLine
        fields = [
            'id',
            'item',
            'item_code',
            'item_name',
            'description',
            'quantity',
            'unit_of_measurement',
            'unit_price',
            'discount_amount',
            'tax_code',
            'tax_rate',
            'tax_amount',
            'line_total',
            'custom_fields',
            'revenue_account',
        ]


class InvoiceTaxLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceTaxLine
        fields = [
            'id',
            'tax_type',
            'rate',
            'base_amount',
            'tax_amount',
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_code = serializers.CharField(source='client.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_code = serializers.CharField(source='category.code', read_only=True, default=None)
    template_name = serializers.CharField(source='template.template_name', read_only=True, default=None)
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    is_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'invoice_type',
            'category',
            'category_name',
            'category_code',
            'description',
            'client',
            'client_name',
            'client_code',
            'template',
            'template_name',
            'currency',
            'exchange_rate',
            'issue_date',
            'due_date',
            'billing_period_start',
            'billing_period_end',
            'reference_number',
            'status',
            'subtotal',
            'discount_amount',
            'tax_amount',
            'total_amount',
            'amount_paid',
            'balance_due',
            'is_paid',
            'custom_fields',
            'created_at',
            'updated_at',
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_code = serializers.CharField(source='client.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_code = serializers.CharField(source='category.code', read_only=True, default=None)
    template_name = serializers.CharField(source='template.template_name', read_only=True, default=None)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    tax_lines = InvoiceTaxLineSerializer(many=True, read_only=True)
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    is_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'invoice_type',
            'category',
            'category_name',
            'category_code',
            'description',
            'client',
            'client_name',
            'client_code',
            'template',
            'template_name',
            'currency',
            'exchange_rate',
            'issue_date',
            'due_date',
            'billing_period_start',
            'billing_period_end',
            'reference_number',
            'status',
            'subtotal',
            'discount_amount',
            'tax_amount',
            'total_amount',
            'amount_paid',
            'balance_due',
            'is_paid',
            'custom_fields',
            'notes',
            'terms_and_conditions',
            'footer_text',
            'journal_entry',
            'parent_invoice',
            'lines',
            'tax_lines',
            'created_at',
            'updated_at',
        ]


class InvoiceLineCreateInputSerializer(serializers.Serializer):
    item_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit_of_measurement = serializers.CharField(max_length=50, default='Unit')
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    discount_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tax_code = serializers.CharField(max_length=50, default='VAT_STANDARD')
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.1500'))
    custom_fields = serializers.DictField(required=False, default=dict)
    revenue_account_id = serializers.UUIDField(required=False, allow_null=True)


class InvoiceCreateSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    invoice_type = serializers.ChoiceField(choices=InvoiceType.choices, default=InvoiceType.STANDARD)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    template_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, default='GHS')
    exchange_rate = serializers.DecimalField(max_digits=18, decimal_places=6, default=Decimal('1.000000'))
    billing_period_start = serializers.DateField(required=False, allow_null=True)
    billing_period_end = serializers.DateField(required=False, allow_null=True)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    invoice_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    lines = InvoiceLineCreateInputSerializer(many=True)
    custom_fields = serializers.DictField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True, default='')
    footer_text = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    auto_calculate_tax = serializers.BooleanField(default=True)


class CreditNoteCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
    credit_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)


class InvoiceVoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class ApplyPresetSerializer(serializers.Serializer):
    preset_code = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    template_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    make_default = serializers.BooleanField(default=False)


class TemplatePresetSerializer(serializers.Serializer):
    preset_code = serializers.CharField()
    template_name = serializers.CharField()
    layout_style = serializers.CharField()
    primary_color = serializers.CharField()
    secondary_color = serializers.CharField()
    accent_color = serializers.CharField()
    invoice_title = serializers.CharField()
    default_notes = serializers.CharField(required=False, default='')
    default_terms = serializers.CharField(required=False, default='')
    footer_text = serializers.CharField(required=False, default='')
    header_custom_fields = serializers.ListField()
    line_custom_fields = serializers.ListField()


class InvoicingBuilderPreviewInputSerializer(serializers.Serializer):
    template_data = serializers.DictField()
    sample_invoice = serializers.DictField(required=False, default=dict)


class RecurringScheduleSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    template_name = serializers.CharField(source='template.template_name', read_only=True, default=None)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    client_id = serializers.UUIDField(write_only=True)
    template_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = RecurringSchedule
        fields = [
            'id',
            'schedule_name',
            'client_id',
            'client_name',
            'template_id',
            'template_name',
            'category_id',
            'category_name',
            'frequency',
            'start_date',
            'end_date',
            'next_run_date',
            'auto_issue',
            'auto_email',
            'invoice_payload',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'next_run_date', 'created_at', 'updated_at']
