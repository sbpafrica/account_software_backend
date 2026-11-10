from rest_framework import serializers
from .models import PayrollBatch


class PayrollBatchOutputSerializer(serializers.ModelSerializer):
    total_funding_required = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = PayrollBatch
        fields = '__all__'


class PayrollBatchCreateInputSerializer(serializers.Serializer):
    batch_code = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField()
    client_name = serializers.CharField(max_length=255)
    country_code = serializers.CharField(max_length=2, default='GH')
    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2020)
    total_net_salaries = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_statutory_taxes = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_management_fee = serializers.DecimalField(max_digits=18, decimal_places=4)


class PayrollBatchUpdateInputSerializer(serializers.Serializer):
    client_name = serializers.CharField(max_length=255, required=False)
    month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    year = serializers.IntegerField(min_value=2020, required=False)
    total_net_salaries = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    total_statutory_taxes = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    total_management_fee = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    status = serializers.CharField(max_length=30, required=False)


class ClientEscrowBalanceOutputSerializer(serializers.Serializer):
    client_id = serializers.CharField()
    available_escrow_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
