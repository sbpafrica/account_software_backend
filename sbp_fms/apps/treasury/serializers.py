from decimal import Decimal
from rest_framework import serializers
from .models import (
    BankAccount, BankTransaction,
    BankStatement, BankStatementLine,
    BankReconciliation
)


# ============================================================================
# 1. BANK ACCOUNTS & TRANSACTIONS
# ============================================================================

class BankAccountOutputSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source='gl_account.code', read_only=True)
    gl_account_name = serializers.CharField(source='gl_account.name', read_only=True)

    class Meta:
        model = BankAccount
        fields = '__all__'


class BankAccountCreateInputSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=50)
    branch_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    swift_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    currency = serializers.CharField(max_length=3, default='GHS')
    country_code = serializers.CharField(max_length=2, default='GH')
    gl_account_id = serializers.UUIDField()


class BankAccountUpdateInputSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=100, required=False)
    branch_name = serializers.CharField(max_length=100, required=False)
    swift_code = serializers.CharField(max_length=50, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    country_code = serializers.CharField(max_length=2, required=False)
    is_active = serializers.BooleanField(required=False)


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


# ============================================================================
# 2. CASHBOOK SERIALIZERS
# ============================================================================

class CashbookEntryOutputSerializer(serializers.Serializer):
    id = serializers.CharField()
    journal_entry_id = serializers.CharField()
    entry_number = serializers.CharField()
    date = serializers.CharField()
    description = serializers.CharField()
    source_module = serializers.CharField()
    source_reference_id = serializers.CharField()
    cost_centre = serializers.CharField(allow_null=True)
    debit = serializers.DecimalField(max_digits=18, decimal_places=4)
    credit = serializers.DecimalField(max_digits=18, decimal_places=4)
    running_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_reconciled = serializers.BooleanField()


class CashbookOutputSerializer(serializers.Serializer):
    bank_account_id = serializers.CharField(allow_null=True)
    bank_name = serializers.CharField(allow_blank=True)
    account_number = serializers.CharField(allow_blank=True)
    gl_account_id = serializers.CharField()
    gl_account_code = serializers.CharField()
    gl_account_name = serializers.CharField()
    currency = serializers.CharField()
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_debits = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_credits = serializers.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    entries = CashbookEntryOutputSerializer(many=True)


# ============================================================================
# 3. BANK STATEMENT SERIALIZERS
# ============================================================================

class BankStatementLineOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankStatementLine
        fields = '__all__'


class BankStatementOutputSerializer(serializers.ModelSerializer):
    lines = BankStatementLineOutputSerializer(many=True, read_only=True)
    bank_name = serializers.CharField(source='bank_account.bank_name', read_only=True)
    account_number = serializers.CharField(source='bank_account.account_number', read_only=True)

    class Meta:
        model = BankStatement
        fields = '__all__'


class BankStatementLineInputSerializer(serializers.Serializer):
    transaction_date = serializers.DateField()
    value_date = serializers.DateField(required=False, allow_null=True)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    debit = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=Decimal('0.0000'))
    credit = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=Decimal('0.0000'))
    running_balance = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, allow_null=True)


class BankStatementImportInputSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    statement_date = serializers.DateField(required=False, allow_null=True)
    file_name = serializers.CharField(max_length=255, required=False, default='')
    csv_content = serializers.CharField(required=False, allow_blank=True, default='')
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=Decimal('0.0000'))
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=Decimal('0.0000'))
    lines = BankStatementLineInputSerializer(many=True, required=False, default=list)


# ============================================================================
# 4. RECONCILIATION SERIALIZERS
# ============================================================================

class BankReconciliationSummaryOutputSerializer(serializers.Serializer):
    bank_account_id = serializers.CharField()
    bank_name = serializers.CharField()
    account_number = serializers.CharField()
    gl_account_code = serializers.CharField()
    statement_date = serializers.CharField()
    statement_ending_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    deposits_in_transit_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    deposits_in_transit = serializers.ListField(child=serializers.DictField())
    outstanding_cheques_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    outstanding_cheques = serializers.ListField(child=serializers.DictField())
    adjusted_bank_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    gl_book_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    unrecorded_bank_credits_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    unrecorded_bank_credits = serializers.ListField(child=serializers.DictField())
    unrecorded_bank_debits_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    unrecorded_bank_debits = serializers.ListField(child=serializers.DictField())
    adjusted_book_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    reconciled_difference = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_balanced = serializers.BooleanField()


class BankReconciliationOutputSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source='bank_account.bank_name', read_only=True)
    account_number = serializers.CharField(source='bank_account.account_number', read_only=True)
    reconciled_by_email = serializers.EmailField(source='reconciled_by.email', read_only=True)

    class Meta:
        model = BankReconciliation
        fields = '__all__'


class ReconciliationAutoMatchInputSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    tolerance_days = serializers.IntegerField(default=3, required=False)


class ReconciliationAutoMatchOutputSerializer(serializers.Serializer):
    matched_count = serializers.IntegerField()
    total_matched_amount = serializers.DecimalField(max_digits=18, decimal_places=4)


class ReconciliationManualMatchInputSerializer(serializers.Serializer):
    statement_line_id = serializers.UUIDField()
    journal_line_id = serializers.UUIDField()


class ReconciliationAdjustmentJournalInputSerializer(serializers.Serializer):
    statement_line_id = serializers.UUIDField()
    offset_account_id = serializers.UUIDField()
    description = serializers.CharField(required=False, allow_blank=True, default='')


class BankReconciliationSaveInputSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    statement_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ============================================================================
# 5. LIQUIDITY FORECAST & WEBHOOK
# ============================================================================

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


# ============================================================================
# 6. DIRECT BANK FEED (FNB / OPEN BANKING) SERIALIZERS
# ============================================================================

from .models import BankFeedConnection, BankFeedProvider, BankFeedStatus


class BankFeedConfigureInputSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=BankFeedProvider.choices, default=BankFeedProvider.FNB_DIRECT_API)
    client_id = serializers.CharField(required=False, allow_blank=True, default='')
    client_secret = serializers.CharField(required=False, allow_blank=True, default='')
    auto_sync = serializers.BooleanField(default=True)


class BankFeedConnectionOutputSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source='bank_account.bank_name', read_only=True)
    account_number = serializers.CharField(source='bank_account.account_number', read_only=True)

    class Meta:
        model = BankFeedConnection
        fields = [
            'id', 'bank_account', 'bank_name', 'account_number', 'provider',
            'status', 'client_id', 'client_secret_masked', 'institution_name',
            'account_number_masked', 'last_synced_at',
            'last_sync_message', 'auto_sync', 'created_at', 'updated_at'
        ]


class BankFeedConnectSessionOutputSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    bank_name = serializers.CharField()
    account_number = serializers.CharField()
    currency = serializers.CharField()
    mono_public_key = serializers.CharField()
    is_connected = serializers.BooleanField()
    connected_institution = serializers.CharField(allow_blank=True)
    last_synced_at = serializers.CharField(allow_null=True)
    provider = serializers.CharField()


class BankFeedExchangeTokenInputSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="One-time authentication code returned by the Mono Connect frontend modal."
    )
    provider = serializers.ChoiceField(
        choices=BankFeedProvider.choices,
        default=BankFeedProvider.MONO,
        required=False,
        help_text="Open banking aggregator provider."
    )


class BankFeedSyncInputSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)


class BankFeedSyncOutputSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    bank_account = serializers.CharField()
    statement_id = serializers.CharField()
    transactions_fetched = serializers.IntegerField()
    auto_matched_count = serializers.IntegerField()
    synced_at = serializers.CharField()
    status = serializers.CharField()

