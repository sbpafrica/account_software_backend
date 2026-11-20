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
    country_code = serializers.CharField(max_length=2, default='GH', required=False)
    gross_salary = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    taxable_income = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)

    def validate(self, attrs):
        if not attrs.get('gross_salary') and not attrs.get('taxable_income'):
            raise serializers.ValidationError("Either 'gross_salary' or 'taxable_income' must be provided.")
        return attrs


class TaxCalculationOutputSerializer(serializers.Serializer):
    employee_ssnit = serializers.DecimalField(max_digits=18, decimal_places=4)
    employer_ssnit = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_ssnit_liability = serializers.DecimalField(max_digits=18, decimal_places=4)


class IndirectTaxCalculatorInputSerializer(serializers.Serializer):
    taxable_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    include_covid_levy = serializers.BooleanField(default=True, required=False)


class TaxCalculationOutputSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2)
    gross_salary = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    employee_ssnit = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    employer_ssnit = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    total_ssnit_liability = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    taxable_income = serializers.DecimalField(max_digits=18, decimal_places=4)
    paye_tax = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_salary = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    effective_paye_rate_pct = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    paye_breakdown = serializers.ListField(child=serializers.DictField(), required=False)


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


# ==============================================================================
# SSNIT STATUTORY PENSION RETURN & SCHEDULE SERIALIZERS (ACT 766)
# ==============================================================================
class SSNITEmployeeItemInputSerializer(serializers.Serializer):
    employee_name = serializers.CharField(max_length=255)
    ssnit_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    ghana_card_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    gross_salary = serializers.DecimalField(max_digits=18, decimal_places=4)


class SSNITScheduleGenerateInputSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False, allow_null=True)
    employer_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    employer_ssnit_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    trustee_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    employees = serializers.ListField(
        child=SSNITEmployeeItemInputSerializer(),
        required=False,
        default=list
    )


class SSNITEmployeeScheduleItemOutputSerializer(serializers.Serializer):
    serial_no = serializers.IntegerField()
    employee_name = serializers.CharField()
    ssnit_number = serializers.CharField()
    ghana_card_number = serializers.CharField()
    gross_salary = serializers.DecimalField(max_digits=18, decimal_places=2)
    employee_contribution = serializers.DecimalField(max_digits=18, decimal_places=2)
    employer_contribution = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_contribution = serializers.DecimalField(max_digits=18, decimal_places=2)
    tier_1_ssnit = serializers.DecimalField(max_digits=18, decimal_places=2)
    tier_2_trustee = serializers.DecimalField(max_digits=18, decimal_places=2)


class SSNITScheduleOutputSerializer(serializers.Serializer):
    employer_name = serializers.CharField()
    employer_ssnit_number = serializers.CharField()
    trustee_name = serializers.CharField(required=False, default='')
    period_month = serializers.IntegerField()
    period_year = serializers.IntegerField()
    period_label = serializers.CharField()
    submission_deadline = serializers.CharField()
    days_until_deadline = serializers.IntegerField()
    is_overdue = serializers.BooleanField()
    statutory_penalty_clause = serializers.CharField()
    total_employees = serializers.IntegerField()
    total_gross_salaries = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_employee_contribution = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_employer_contribution = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_tier_1_payable_to_ssnit = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_tier_2_payable_to_trustee = serializers.DecimalField(max_digits=18, decimal_places=2)
    grand_total_contributions = serializers.DecimalField(max_digits=18, decimal_places=2)
    schedule = serializers.ListField(child=SSNITEmployeeScheduleItemOutputSerializer())


class SSNITClientSummaryItemSerializer(serializers.Serializer):
    client_id = serializers.CharField()
    client_name = serializers.CharField()
    client_code = serializers.CharField(required=False, allow_blank=True, default='')
    employer_ssnit_number = serializers.CharField(required=False, allow_blank=True, default='')
    batch_count = serializers.IntegerField()
    batch_status = serializers.CharField()
    is_funded = serializers.BooleanField()
    gross_salaries = serializers.DecimalField(max_digits=18, decimal_places=2)
    employee_share = serializers.DecimalField(max_digits=18, decimal_places=2)
    employer_share = serializers.DecimalField(max_digits=18, decimal_places=2)
    tier_1_ssnit = serializers.DecimalField(max_digits=18, decimal_places=2)
    tier_2_trustee = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_ssnit_liability = serializers.DecimalField(max_digits=18, decimal_places=2)


class SSNITReturnSummaryOutputSerializer(serializers.Serializer):
    client_id = serializers.CharField(required=False, allow_null=True)
    employer_name = serializers.CharField()
    employer_ssnit_number = serializers.CharField()
    period_month = serializers.IntegerField()
    period_year = serializers.IntegerField()
    period_label = serializers.CharField()
    submission_deadline = serializers.CharField()
    days_until_deadline = serializers.IntegerField()
    is_overdue = serializers.BooleanField()
    total_clients = serializers.IntegerField(default=1)
    total_employees = serializers.IntegerField()
    total_gross_salaries = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_employee_share = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_employer_share = serializers.DecimalField(max_digits=18, decimal_places=2)
    tier_1_payable_ssnit = serializers.DecimalField(max_digits=18, decimal_places=2)
    tier_2_payable_trustee = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_statutory_pension_liability = serializers.DecimalField(max_digits=18, decimal_places=2)
    statutory_penalty_clause = serializers.CharField()
    clients = serializers.ListField(child=SSNITClientSummaryItemSerializer(), required=False, default=list)


class SSNITPaymentVoucherCreateInputSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False, allow_null=True)
    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    remittance_type = serializers.ChoiceField(
        choices=['TIER_1_SSNIT', 'TIER_2_TRUSTEE', 'COMBINED'],
        default='TIER_1_SSNIT',
        help_text="Specifies statutory destination: TIER_1_SSNIT (13.5% directly to SSNIT), TIER_2_TRUSTEE (5.0% to Corporate Trustee), or COMBINED (18.5%)."
    )
    trustee_name = serializers.CharField(required=False, allow_blank=True, default='')
    bank_account_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

