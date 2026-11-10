from decimal import Decimal
from rest_framework import serializers
from .models import TaxRule


class TaxRuleOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = '__all__'


class TaxRuleCreateInputSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2, default='GH')
    tax_type = serializers.CharField(max_length=20)
    bracket_min = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
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


class IndirectTaxCalculatorInputSerializer(serializers.Serializer):
    taxable_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    include_covid_levy = serializers.BooleanField(default=True, required=False)


class IndirectTaxCalculatorOutputSerializer(serializers.Serializer):
    taxable_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    nhil_rate = serializers.DecimalField(max_digits=6, decimal_places=4)
    nhil_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    getfund_rate = serializers.DecimalField(max_digits=6, decimal_places=4)
    getfund_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    covid_levy_rate = serializers.DecimalField(max_digits=6, decimal_places=4)
    covid_levy_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_levies = serializers.DecimalField(max_digits=18, decimal_places=4)
    vat_base = serializers.DecimalField(max_digits=18, decimal_places=4)
    vat_rate = serializers.DecimalField(max_digits=6, decimal_places=4)
    vat_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_tax = serializers.DecimalField(max_digits=18, decimal_places=4)
    grand_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    effective_tax_rate_pct = serializers.DecimalField(max_digits=6, decimal_places=2)


class VATReturnSummaryOutputSerializer(serializers.Serializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    country_code = serializers.CharField()
    taxable_supplies_sales = serializers.DecimalField(max_digits=18, decimal_places=4)
    output_tax_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    output_nhil = serializers.DecimalField(max_digits=18, decimal_places=4)
    output_getfund = serializers.DecimalField(max_digits=18, decimal_places=4)
    output_covid_levy = serializers.DecimalField(max_digits=18, decimal_places=4)
    output_vat = serializers.DecimalField(max_digits=18, decimal_places=4)
    taxable_purchases = serializers.DecimalField(max_digits=18, decimal_places=4)
    input_tax_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_vat_payable = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_refund_credit = serializers.BooleanField()
    withholding_tax_payable = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_statutory_liability = serializers.DecimalField(max_digits=18, decimal_places=4)
