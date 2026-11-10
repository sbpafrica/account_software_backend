from rest_framework import serializers
from .models import Client, ClientInvoice


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


class ClientUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    code = serializers.CharField(max_length=50, required=False)
    country_code = serializers.CharField(max_length=2, required=False)
    credit_limit = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    payment_terms_days = serializers.IntegerField(required=False)


class ClientInvoiceOutputSerializer(serializers.ModelSerializer):
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = ClientInvoice
        fields = '__all__'


class ClientInvoiceCreateInputSerializer(serializers.Serializer):
    invoice_number = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField()
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=4)


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
