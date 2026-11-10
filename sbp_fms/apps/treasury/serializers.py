from rest_framework import serializers
from .models import BankAccount, BankTransaction


class BankAccountOutputSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source='gl_account.code', read_only=True)
    gl_account_name = serializers.CharField(source='gl_account.name', read_only=True)

    class Meta:
        model = BankAccount
        fields = '__all__'


class BankAccountCreateInputSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=50)
    currency = serializers.CharField(max_length=3, default='GHS')
    country_code = serializers.CharField(max_length=2, default='GH')
    gl_account_id = serializers.UUIDField()


class BankAccountUpdateInputSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=100, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    country_code = serializers.CharField(max_length=2, required=False)


class BankTransactionOutputSerializer(serializers.ModelSerializer):
    bank_account_number = serializers.CharField(source='bank_account.account_number', read_only=True)
    bank_name = serializers.CharField(source='bank_account.bank_name', read_only=True)

    class Meta:
        model = BankTransaction
        fields = '__all__'


class BankTransactionCreateInputSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    transaction_date = serializers.DateField()
    bank_reference = serializers.CharField(max_length=100)
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_reconciled = serializers.BooleanField(default=False, required=False)


class BankTransactionUpdateInputSerializer(serializers.Serializer):
    transaction_date = serializers.DateField(required=False)
    description = serializers.CharField(required=False)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    is_reconciled = serializers.BooleanField(required=False)


class CashForecastOutputSerializer(serializers.Serializer):
    current_available_cash = serializers.DecimalField(max_digits=18, decimal_places=4)
    forecast_30_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    forecast_60_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    forecast_90_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    pending_supplier_payables = serializers.DecimalField(max_digits=18, decimal_places=4)


class BankWebhookInputSerializer(serializers.Serializer):
    event_type = serializers.CharField(required=False, default='TRANSACTION_NOTIFICATION')
    data = serializers.DictField(required=False, default=dict)


class BankWebhookOutputSerializer(serializers.Serializer):
    status = serializers.CharField()
