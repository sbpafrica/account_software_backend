from rest_framework import serializers
from .models import (
    Client, ClientInvoice, ClientInvoiceLine, PaymentReceipt, ReceiptAllocation,
    ClientInvoiceTemplate, InvoiceLayoutStyle
)


# ==============================================================================
# INVOICE TEMPLATE & BUILDER SERIALIZERS
# ==============================================================================

class ClientInvoiceTemplateOutputSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = ClientInvoiceTemplate
        fields = '__all__'


class ClientInvoiceTemplateCreateInputSerializer(serializers.Serializer):
    template_name = serializers.CharField(max_length=100)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    layout_style = serializers.ChoiceField(choices=InvoiceLayoutStyle.choices, default=InvoiceLayoutStyle.MODERN)
    primary_color = serializers.CharField(max_length=20, default='#102a43')
    secondary_color = serializers.CharField(max_length=20, default='#243b53')
    accent_color = serializers.CharField(max_length=20, default='#0ea5e9')
    logo_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    show_logo = serializers.BooleanField(default=True)
    font_family = serializers.CharField(max_length=100, default='Inter, sans-serif')
    invoice_title = serializers.CharField(max_length=100, default='TAX INVOICE')
    show_tax_breakdown = serializers.BooleanField(default=True)
    show_bank_details = serializers.BooleanField(default=True)
    show_due_date_badge = serializers.BooleanField(default=True)
    default_notes = serializers.CharField(required=False, allow_blank=True, default='Thank you for partnering with SBP Africa Group.')
    default_terms = serializers.CharField(required=False, allow_blank=True, default='Payment is due within payment terms. All bank charges borne by payer.')
    footer_text = serializers.CharField(max_length=255, required=False, allow_blank=True, default='SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg')
    custom_field_definitions = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text="Custom field definitions: list of dicts with key, label, type, required, default_value, placeholder"
    )
    is_default = serializers.BooleanField(default=False)
    is_active = serializers.BooleanField(default=True)


class ClientInvoiceTemplateUpdateInputSerializer(serializers.Serializer):
    template_name = serializers.CharField(max_length=100, required=False)
    layout_style = serializers.ChoiceField(choices=InvoiceLayoutStyle.choices, required=False)
    primary_color = serializers.CharField(max_length=20, required=False)
    secondary_color = serializers.CharField(max_length=20, required=False)
    accent_color = serializers.CharField(max_length=20, required=False)
    logo_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    show_logo = serializers.BooleanField(required=False)
    font_family = serializers.CharField(max_length=100, required=False)
    invoice_title = serializers.CharField(max_length=100, required=False)
    show_tax_breakdown = serializers.BooleanField(required=False)
    show_bank_details = serializers.BooleanField(required=False)
    show_due_date_badge = serializers.BooleanField(required=False)
    default_notes = serializers.CharField(required=False, allow_blank=True)
    default_terms = serializers.CharField(required=False, allow_blank=True)
    footer_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    custom_field_definitions = serializers.ListField(child=serializers.DictField(), required=False)
    is_default = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class InvoiceBuilderPreviewInputSerializer(serializers.Serializer):
    template = ClientInvoiceTemplateCreateInputSerializer(required=False)
    template_id = serializers.UUIDField(required=False, allow_null=True)
    sample_invoice = serializers.DictField(required=False, default=dict)


class ClientOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'


class ClientCreateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=50)
    country_code = serializers.CharField(max_length=2, default='GH')
    credit_limit = serializers.DecimalField(max_digits=18, decimal_places=4, default=50000.0)
    payment_terms_days = serializers.IntegerField(default=30)
    category = serializers.CharField(max_length=50, required=False, default='CORPORATE')
    tax_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    registration_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    contact_person = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    telephone = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    billing_address = serializers.CharField(required=False, allow_blank=True, default='')
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=0.0)


class ClientUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    code = serializers.CharField(max_length=50, required=False)
    country_code = serializers.CharField(max_length=2, required=False)
    credit_limit = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    payment_terms_days = serializers.IntegerField(required=False)
    tax_id = serializers.CharField(max_length=50, required=False)
    contact_person = serializers.CharField(max_length=100, required=False)
    telephone = serializers.CharField(max_length=50, required=False)
    email = serializers.EmailField(required=False)
    billing_address = serializers.CharField(required=False)


class ClientInvoiceLineOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientInvoiceLine
        fields = '__all__'


class ClientInvoiceLineInputSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, default=1.0)
    unit_of_measurement = serializers.CharField(max_length=20, default='Unit')
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4)
    discount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=0.0)
    tax_code = serializers.CharField(max_length=20, required=False, default='EXEMPT')
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=4, required=False, default=0.0)
    custom_fields = serializers.DictField(required=False, default=dict)


class ClientInvoiceOutputSerializer(serializers.ModelSerializer):
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    template_name = serializers.CharField(source='template.template_name', read_only=True, default=None)
    lines = ClientInvoiceLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = ClientInvoice
        fields = '__all__'


class ClientInvoiceCreateInputSerializer(serializers.Serializer):
    invoice_number = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField()
    template_id = serializers.UUIDField(required=False, allow_null=True)
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True)
    custom_fields = serializers.DictField(required=False, default=dict)
    lines = ClientInvoiceLineInputSerializer(many=True, required=False, default=list)


class ClientInvoiceUpdateInputSerializer(serializers.Serializer):
    issue_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
    template_id = serializers.UUIDField(required=False, allow_null=True)
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    amount_paid = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    status = serializers.CharField(max_length=20, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True)
    custom_fields = serializers.DictField(required=False)


class ApplyPresetInputSerializer(serializers.Serializer):
    preset_code = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    template_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_default = serializers.BooleanField(default=False)


class ClientInvoiceRenderOutputSerializer(serializers.Serializer):
    invoice = serializers.DictField()
    client = serializers.DictField()
    company = serializers.DictField()
    bank_accounts = serializers.ListField(child=serializers.DictField())
    template = serializers.DictField()
    totals = serializers.DictField()
    lines = serializers.ListField(child=serializers.DictField())


class AgingReportOutputSerializer(serializers.Serializer):
    country_code = serializers.CharField()
    current_0_30_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    overdue_31_60_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    overdue_61_90_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    overdue_90_plus_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_receivables = serializers.DecimalField(max_digits=18, decimal_places=4)


class ReceiptAllocationOutputSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = ReceiptAllocation
        fields = '__all__'


class ReceiptAllocationInputSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)


class PaymentReceiptOutputSerializer(serializers.ModelSerializer):
    allocations = ReceiptAllocationOutputSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    bank_account_number = serializers.CharField(source='bank_account.account_number', read_only=True)

    class Meta:
        model = PaymentReceipt
        fields = '__all__'


class PaymentReceiptCreateInputSerializer(serializers.Serializer):
    receipt_number = serializers.CharField(max_length=50)
    receipt_date = serializers.DateField(required=False)
    client_id = serializers.UUIDField()
    amount_received = serializers.DecimalField(max_digits=18, decimal_places=4)
    payment_method = serializers.CharField(max_length=30, required=False, default='BANK_TRANSFER')
    bank_account_id = serializers.UUIDField()
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    allocations = ReceiptAllocationInputSerializer(many=True, required=False, default=list)


class CustomerStatementTransactionSerializer(serializers.Serializer):
    date = serializers.CharField()
    reference = serializers.CharField()
    type = serializers.CharField()
    billed = serializers.DecimalField(max_digits=18, decimal_places=4)
    received = serializers.DecimalField(max_digits=18, decimal_places=4)
    balance = serializers.DecimalField(max_digits=18, decimal_places=4)


class CustomerStatementOutputSerializer(serializers.Serializer):
    client_id = serializers.CharField()
    client_name = serializers.CharField()
    client_code = serializers.CharField()
    country_code = serializers.CharField()
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    transactions = CustomerStatementTransactionSerializer(many=True)


class InvoicePaystackInitializeInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True, help_text="Amount to pay. Defaults to invoice balance due.")
    callback_url = serializers.URLField(required=False, allow_null=True, help_text="Frontend redirection URL after Paystack checkout completion.")


class InvoicePaystackInitializeOutputSerializer(serializers.Serializer):
    authorization_url = serializers.URLField(help_text="Paystack secure checkout URL to redirect the user to.")
    access_code = serializers.CharField(help_text="Paystack checkout access code.")
    reference = serializers.CharField(help_text="Unique transaction reference sent to Paystack.")
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency = serializers.CharField()
    invoice_number = serializers.CharField()


class InvoicePaystackVerifyInputSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100, help_text="Paystack transaction reference received upon checkout completion.")


class InvoicePaystackVerifyOutputSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    receipt = PaymentReceiptOutputSerializer(allow_null=True)
    invoice = ClientInvoiceOutputSerializer(allow_null=True)


