from decimal import Decimal
from rest_framework import serializers
from .models import Contract, ContractStatus


class ContractCreateInputSerializer(serializers.Serializer):
    contract_number = serializers.CharField(max_length=50)
    client_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    total_contract_value = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    cost_centre = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class ContractUpdateInputSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, max_length=255)
    status = serializers.ChoiceField(choices=ContractStatus.choices, required=False)
    total_contract_value = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    cost_centre = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class ContractOutputSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'client', 'client_name', 'title',
            'start_date', 'end_date', 'total_contract_value', 'status',
            'cost_centre', 'notes', 'created_at'
        ]


class ContractProfitabilityOutputSerializer(serializers.Serializer):
    contract_id = serializers.UUIDField()
    contract_number = serializers.CharField()
    contract_title = serializers.CharField()
    client_id = serializers.UUIDField()
    client_name = serializers.CharField()
    status = serializers.CharField()
    total_contract_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    cost_centre = serializers.CharField()
    billed_revenue = serializers.DecimalField(max_digits=18, decimal_places=4)
    cash_collected = serializers.DecimalField(max_digits=18, decimal_places=4)
    ar_outstanding = serializers.DecimalField(max_digits=18, decimal_places=4)
    direct_expenses = serializers.DecimalField(max_digits=18, decimal_places=4)
    direct_labour = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_direct_costs = serializers.DecimalField(max_digits=18, decimal_places=4)
    gross_profit = serializers.DecimalField(max_digits=18, decimal_places=4)
    gross_margin_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    contract_realization_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    is_profitable = serializers.BooleanField()
