from decimal import Decimal
from rest_framework import serializers
from .models import Budget, BudgetLine, BudgetStatus


class BudgetLineInputSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    period_month = serializers.IntegerField(required=False, allow_null=True)
    planned_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class BudgetCreateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    financial_year = serializers.IntegerField()
    department = serializers.CharField(required=False, allow_blank=True, default='')
    cost_centre = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    lines = BudgetLineInputSerializer(many=True, required=False)


class BudgetLineOutputSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = BudgetLine
        fields = ['id', 'account', 'account_code', 'account_name', 'period_month', 'planned_amount', 'notes']


class BudgetOutputSerializer(serializers.ModelSerializer):
    lines = BudgetLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'name', 'financial_year', 'department', 'cost_centre',
            'status', 'total_budget', 'notes', 'lines', 'created_at'
        ]


class PreCommitmentCheckInputSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    department = serializers.CharField(required=False, allow_blank=True)
    cost_centre = serializers.CharField(required=False, allow_blank=True)
    financial_year = serializers.IntegerField(required=False, allow_null=True)


class BudgetVarianceLineReportSerializer(serializers.Serializer):
    line_id = serializers.CharField()
    account_id = serializers.CharField()
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    planned_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    actual_spent = serializers.DecimalField(max_digits=18, decimal_places=4)
    pending_commitments = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_absorbed = serializers.DecimalField(max_digits=18, decimal_places=4)
    available_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    utilization_rate_pct = serializers.DecimalField(max_digits=6, decimal_places=2)
    is_overbudget = serializers.BooleanField()


class BudgetVarianceReportOutputSerializer(serializers.Serializer):
    budget_id = serializers.CharField()
    budget_name = serializers.CharField()
    financial_year = serializers.IntegerField()
    department = serializers.CharField(allow_blank=True)
    cost_centre = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    lines = BudgetVarianceLineReportSerializer(many=True)
    total_planned = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_actual = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_commitments = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_available_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    overall_utilization_pct = serializers.DecimalField(max_digits=6, decimal_places=2)
    is_healthy = serializers.BooleanField()


class PreCommitmentCheckOutputSerializer(serializers.Serializer):
    allowed = serializers.BooleanField()
    has_budget_constraint = serializers.BooleanField()
    planned_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    actual_spent = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    pending_commitments = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    requested_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    projected_available_balance = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    message = serializers.CharField()
