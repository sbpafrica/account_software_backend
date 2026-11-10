from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import BaseModel
from apps.ledger.models import Account


class BankAccount(BaseModel):
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, unique=True)
    branch_name = models.CharField(max_length=100, blank=True, default='')
    swift_code = models.CharField(max_length=50, blank=True, default='')
    currency = models.CharField(max_length=3, default='GHS')
    country_code = models.CharField(max_length=2, default='GH')
    gl_account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name='bank_account')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bank_name} - {self.account_number} ({self.currency})"


class BankTransaction(BaseModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_date = models.DateField(db_index=True)
    bank_reference = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    is_reconciled = models.BooleanField(default=False, db_index=True)
    reconciled_journal_line = models.ForeignKey(
        'ledger.JournalLine',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reconciled_bank_transactions'
    )

    def __str__(self):
        return f"{self.bank_reference} ({self.amount}) - Reconciled: {self.is_reconciled}"


class BankStatement(BaseModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='statements')
    statement_date = models.DateField(db_index=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    closing_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    file_name = models.CharField(max_length=255, blank=True, default='')
    total_lines = models.PositiveIntegerField(default=0)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-statement_date', '-created_at']

    def __str__(self):
        return f"Statement {self.bank_account.bank_name} - {self.statement_date} ({self.file_name})"


class BankStatementLine(BaseModel):
    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name='lines')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='statement_lines')
    transaction_date = models.DateField(db_index=True)
    value_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True, default='', db_index=True)
    description = models.TextField(blank=True, default='')
    debit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))  # Deposits / inflows
    credit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000')) # Withdrawals / charges
    amount = models.DecimalField(max_digits=18, decimal_places=4)  # Net amount: positive for deposits, negative for withdrawals
    running_balance = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    transaction_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_reconciled = models.BooleanField(default=False, db_index=True)
    matched_journal_line = models.ForeignKey(
        'ledger.JournalLine',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reconciled_statement_lines'
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['transaction_date', 'created_at']

    def __str__(self):
        return f"{self.transaction_date} | {self.reference} | {self.amount} (Reconciled: {self.is_reconciled})"


class ReconciliationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    COMPLETED = 'COMPLETED', 'Completed'


class BankReconciliation(BaseModel):
    reconciliation_number = models.CharField(max_length=50, unique=True, db_index=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='reconciliations')
    statement_date = models.DateField(db_index=True)
    statement_ending_balance = models.DecimalField(max_digits=18, decimal_places=4)
    gl_book_balance = models.DecimalField(max_digits=18, decimal_places=4)
    deposits_in_transit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    outstanding_cheques = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    unrecorded_bank_credits = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    unrecorded_bank_debits = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    reconciled_difference = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(
        max_length=20,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.DRAFT,
        db_index=True
    )
    reconciled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-statement_date', '-created_at']

    def __str__(self):
        return f"{self.reconciliation_number} - {self.bank_account.bank_name} ({self.statement_date}) [{self.status}]"


class BankFeedProvider(models.TextChoices):
    MONO = 'MONO', 'Mono Open Banking (West & East Africa)'
    STITCH = 'STITCH', 'Stitch Financial API (Southern Africa)'
    FNB_DIRECT_API = 'FNB_DIRECT_API', 'First National Bank Direct API'
    FNB_HOST_TO_HOST = 'FNB_HOST_TO_HOST', 'First National Bank Host-to-Host (SFTP)'
    OPEN_BANKING = 'OPEN_BANKING', 'Generic Open Banking Aggregator'
    MANUAL_IMPORT = 'MANUAL_IMPORT', 'Manual CSV/Excel Import'


class BankFeedStatus(models.TextChoices):
    CONNECTED = 'CONNECTED', 'Connected & Active'
    DISCONNECTED = 'DISCONNECTED', 'Disconnected'
    SYNCING = 'SYNCING', 'Sync in Progress'
    ERROR = 'ERROR', 'Authentication / Network Error'


class BankFeedConnection(BaseModel):
    bank_account = models.OneToOneField(BankAccount, on_delete=models.CASCADE, related_name='feed_connection')
    provider = models.CharField(max_length=50, choices=BankFeedProvider.choices, default=BankFeedProvider.MONO)
    status = models.CharField(max_length=30, choices=BankFeedStatus.choices, default=BankFeedStatus.DISCONNECTED)
    client_id = models.CharField(max_length=255, blank=True, default='', help_text="Mono Account ID or Provider Client ID")
    client_secret_masked = models.CharField(max_length=255, blank=True, default='')
    institution_name = models.CharField(max_length=150, blank=True, default='', help_text="Connected bank name from provider, e.g. Ecobank Ghana")
    account_number_masked = models.CharField(max_length=50, blank=True, default='', help_text="Masked account number, e.g. ****1234")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_message = models.TextField(blank=True, default='')
    auto_sync = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bank_account.bank_name} Feed ({self.provider}) - Status: {self.status}"

