from rest_framework import serializers
from .models import Client, ClientInvoice, ClientInvoiceLine, PaymentReceipt, ReceiptAllocation


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


class ClientInvoiceOutputSerializer(serializers.ModelSerializer):
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    lines = ClientInvoiceLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = ClientInvoice
        fields = '__all__'


class ClientInvoiceCreateInputSerializer(serializers.Serializer):
    invoice_number = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField()
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    lines = ClientInvoiceLineInputSerializer(many=True, required=False, default=list)


class ClientInvoiceUpdateInputSerializer(serializers.Serializer):
    issue_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    amount_paid = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    status = serializers.CharField(max_length=20, required=False)


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

