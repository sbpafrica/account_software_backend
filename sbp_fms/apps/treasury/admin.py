from django.contrib import admin
from apps.treasury.models import (
    BankAccount, BankTransaction, BankStatement,
    BankStatementLine, BankReconciliation, BankFeedConnection
)


class BankStatementLineInline(admin.TabularInline):
    model = BankStatementLine
    extra = 1


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_number', 'branch_name', 'currency', 'country_code', 'is_active', 'created_at')
    list_filter = ('country_code', 'currency', 'is_active')
    search_fields = ('bank_name', 'account_number')


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('bank_account', 'transaction_date', 'bank_reference', 'amount', 'is_reconciled')
    list_filter = ('is_reconciled', 'bank_account__country_code')
    search_fields = ('bank_reference', 'description')


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    list_display = ('bank_account', 'statement_date', 'start_date', 'end_date', 'opening_balance', 'closing_balance')
    list_filter = ('bank_account__country_code',)
    search_fields = ('bank_account__bank_name',)
    inlines = [BankStatementLineInline]


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ('reconciliation_number', 'bank_account', 'statement_date', 'status', 'created_at')
    list_filter = ('status', 'bank_account__country_code')
    search_fields = ('reconciliation_number',)


@admin.register(BankFeedConnection)
class BankFeedConnectionAdmin(admin.ModelAdmin):
    list_display = ('institution_name', 'bank_account', 'provider', 'status', 'auto_sync', 'last_synced_at')
    list_filter = ('provider', 'status', 'auto_sync')
    search_fields = ('institution_name',)
