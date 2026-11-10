from rest_framework import serializers
from .models import TaxRule


class TaxRuleOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = '__all__'


class TaxRuleCreateInputSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2, default='GH')
    tax_type = serializers.CharField(max_length=20)
    bracket_min = serializers.DecimalField(max_digits=18, decimal_places=4, default=0.0)
    bracket_max = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    rate = serializers.DecimalField(max_digits=5, decimal_places=4)
    effective_from = serializers.DateField()


class TaxRuleUpdateInputSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2, required=False)
    tax_type = serializers.CharField(max_length=20, required=False)
    bracket_min = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    bracket_max = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)
    rate = serializers.DecimalField(max_digits=5, decimal_places=4, required=False)
    effective_from = serializers.DateField(required=False)


class TaxCalculationInputSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2, default='GH')
    gross_salary = serializers.DecimalField(max_digits=18, decimal_places=4)


class TaxCalculationOutputSerializer(serializers.Serializer):
    employee_ssnit = serializers.DecimalField(max_digits=18, decimal_places=4)
    employer_ssnit = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_ssnit_liability = serializers.DecimalField(max_digits=18, decimal_places=4)

