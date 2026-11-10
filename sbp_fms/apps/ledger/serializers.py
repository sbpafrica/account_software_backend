from rest_framework import serializers
from .models import Account, JournalEntry, JournalLine, CompanyProfile, Department, CostCentre

class CompanyProfileOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = '__all__'

class CompanyProfileUpdateInputSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255, required=False)
    registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tax_identification_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_address = serializers.CharField(required=False, allow_blank=True)
    telephone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    base_currency = serializers.CharField(max_length=3, required=False)
    financial_year_start_month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    financial_year_end_month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    default_payment_terms_days = serializers.IntegerField(min_value=0, required=False)
    invoice_prefix = serializers.CharField(max_length=20, required=False)
    voucher_prefix = serializers.CharField(max_length=20, required=False)
    receipt_prefix = serializers.CharField(max_length=20, required=False)
    expense_prefix = serializers.CharField(max_length=20, required=False)
    journal_prefix = serializers.CharField(max_length=20, required=False)

class DepartmentOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'

class DepartmentCreateInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=100)

class CostCentreOutputSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = CostCentre
        fields = '__all__'

class CostCentreCreateInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=100)
    department_id = serializers.UUIDField(required=False, allow_null=True)

class AccountOutputSerializer(serializers.ModelSerializer):
    parent_code = serializers.CharField(source='parent.code', read_only=True)

    class Meta:
        model = Account
        fields = ['id', 'code', 'name', 'account_type', 'subtype', 'parent', 'parent_code', 'currency', 'country_code', 'is_active', 'allow_direct_posting', 'opening_balance', 'opening_balance_date', 'description', 'created_at']

class AccountCreateInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=255)
    account_type = serializers.CharField(max_length=20)
    subtype = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, default='GHS')
    country_code = serializers.CharField(max_length=2, default='GH')
    allow_direct_posting = serializers.BooleanField(required=False, default=True)
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=0.0)
    opening_balance_date = serializers.DateField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')

class AccountUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    account_type = serializers.CharField(max_length=20, required=False)
    subtype = serializers.CharField(max_length=50, required=False)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False)
    country_code = serializers.CharField(max_length=2, required=False)
    is_active = serializers.BooleanField(required=False)
    allow_direct_posting = serializers.BooleanField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)


class JournalLineOutputSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalLine
        fields = ['id', 'account', 'account_code', 'account_name', 'debit', 'credit', 'client_id', 'cost_centre', 'country_code']

class JournalEntryOutputSerializer(serializers.ModelSerializer):
    lines = JournalLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = ['id', 'entry_number', 'posting_date', 'status', 'description', 'source_module', 'source_reference_id', 'created_by', 'approved_by', 'lines', 'created_at']

class JournalLineInputSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    debit = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    credit = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    cost_centre = serializers.CharField(required=False, allow_blank=True)
    country_code = serializers.CharField(max_length=2, default='GH')

class JournalEntryCreateInputSerializer(serializers.Serializer):
    entry_number = serializers.CharField(max_length=50)
    posting_date = serializers.DateField()
    description = serializers.CharField()
    source_module = serializers.CharField(max_length=50)
    source_reference_id = serializers.CharField(max_length=100)
    lines = JournalLineInputSerializer(many=True)

class JournalEntryReverseInputSerializer(serializers.Serializer):
    reason = serializers.CharField()


class TrialBalanceAccountOutputSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    account_type = serializers.CharField()
    total_debit = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_credit = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_balance = serializers.DecimalField(max_digits=18, decimal_places=4)


class TrialBalanceOutputSerializer(serializers.Serializer):
    as_of_date = serializers.CharField()
    country_code = serializers.CharField()
    grand_total_debits = serializers.DecimalField(max_digits=18, decimal_places=4)
    grand_total_credits = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_balanced = serializers.BooleanField()
    accounts = TrialBalanceAccountOutputSerializer(many=True)


class ProfitAndLossOutputSerializer(serializers.Serializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    country_code = serializers.CharField()
    revenue_items = serializers.ListField(child=serializers.DictField())
    total_revenue = serializers.DecimalField(max_digits=18, decimal_places=4)
    cost_of_sales_items = serializers.ListField(child=serializers.DictField())
    total_cost_of_sales = serializers.DecimalField(max_digits=18, decimal_places=4)
    gross_profit = serializers.DecimalField(max_digits=18, decimal_places=4)
    gross_profit_margin_pct = serializers.DecimalField(max_digits=6, decimal_places=2)
    operating_expense_items = serializers.ListField(child=serializers.DictField())
    total_operating_expenses = serializers.DecimalField(max_digits=18, decimal_places=4)
    operating_profit = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_profit = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_margin_pct = serializers.DecimalField(max_digits=6, decimal_places=2)


class BalanceSheetOutputSerializer(serializers.Serializer):
    as_of_date = serializers.CharField()
    country_code = serializers.CharField()
    current_assets = serializers.ListField(child=serializers.DictField())
    total_current_assets = serializers.DecimalField(max_digits=18, decimal_places=4)
    non_current_assets = serializers.ListField(child=serializers.DictField())
    total_non_current_assets = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_assets = serializers.DecimalField(max_digits=18, decimal_places=4)
    current_liabilities = serializers.ListField(child=serializers.DictField())
    total_current_liabilities = serializers.DecimalField(max_digits=18, decimal_places=4)
    non_current_liabilities = serializers.ListField(child=serializers.DictField())
    total_non_current_liabilities = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_liabilities = serializers.DecimalField(max_digits=18, decimal_places=4)
    equity_items = serializers.ListField(child=serializers.DictField())
    total_equity_accounts = serializers.DecimalField(max_digits=18, decimal_places=4)
    current_period_earnings = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_equity = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_liabilities_and_equity = serializers.DecimalField(max_digits=18, decimal_places=4)
    difference = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_balanced = serializers.BooleanField()


class CashFlowStatementOutputSerializer(serializers.Serializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    country_code = serializers.CharField()
    net_income = serializers.DecimalField(max_digits=18, decimal_places=4)
    change_in_receivables = serializers.DecimalField(max_digits=18, decimal_places=4)
    change_in_payables = serializers.DecimalField(max_digits=18, decimal_places=4)
    operating_cash_flow = serializers.DecimalField(max_digits=18, decimal_places=4)
    investing_cash_flow = serializers.DecimalField(max_digits=18, decimal_places=4)
    financing_cash_flow = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_cash_change = serializers.DecimalField(max_digits=18, decimal_places=4)
    beginning_cash = serializers.DecimalField(max_digits=18, decimal_places=4)
    ending_cash = serializers.DecimalField(max_digits=18, decimal_places=4)


class GLAccountStatementOutputSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    code = serializers.CharField()
    name = serializers.CharField()
    account_type = serializers.CharField()
    currency = serializers.CharField()
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_debits = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_credits = serializers.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    entries = serializers.ListField(child=serializers.DictField())


class CEOExecutiveDashboardOutputSerializer(serializers.Serializer):
    as_of_date = serializers.CharField()
    country_code = serializers.CharField()
    liquidity = serializers.DictField()
    receivables = serializers.DictField()
    payables = serializers.DictField()
    profitability = serializers.DictField()
    ratios = serializers.DictField()


