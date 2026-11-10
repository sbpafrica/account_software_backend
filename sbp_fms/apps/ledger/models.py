from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from apps.common.models import BaseModel, TenantModel

class AccountType(models.TextChoices):
    ASSET = 'ASSET', 'Asset (1000-1999)'
    LIABILITY = 'LIABILITY', 'Liability (2000-2999)'
    EQUITY = 'EQUITY', 'Equity (3000-3999)'
    REVENUE = 'REVENUE', 'Revenue (4000-4999)'
    DIRECT_COST = 'DIRECT_COST', 'Direct Cost (5000-5999)'
    OPEX = 'OPEX', 'Operating Expense (6000-6999)'

class CompanyProfile(TenantModel):
    company_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, blank=True, default='')
    tax_identification_number = models.CharField(max_length=100, blank=True, default='')
    business_address = models.TextField(blank=True, default='')
    telephone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    base_currency = models.CharField(max_length=3, default='GHS')
    financial_year_start_month = models.PositiveSmallIntegerField(default=1)
    financial_year_end_month = models.PositiveSmallIntegerField(default=12)
    default_payment_terms_days = models.PositiveSmallIntegerField(default=30)
    invoice_prefix = models.CharField(max_length=20, default='INV-')
    voucher_prefix = models.CharField(max_length=20, default='PV-')
    receipt_prefix = models.CharField(max_length=20, default='REC-')
    expense_prefix = models.CharField(max_length=20, default='EXP-')
    journal_prefix = models.CharField(max_length=20, default='JV-')
    country_code = models.CharField(max_length=2, default='GH')

    def __str__(self):
        return f"{self.company_name} ({self.country_code})"

class Department(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class CostCentre(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='cost_centres')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Account(BaseModel):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    subtype = models.CharField(max_length=50, blank=True, default='')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    currency = models.CharField(max_length=3, default='GHS')
    country_code = models.CharField(max_length=2, default='GH')
    is_active = models.BooleanField(default=True)
    allow_direct_posting = models.BooleanField(default=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    opening_balance_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.currency})"

class JournalEntryStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    POSTED = 'POSTED', 'Posted'
    REVERSED = 'REVERSED', 'Reversed'

class JournalEntry(BaseModel):
    entry_number = models.CharField(max_length=50, unique=True, db_index=True)
    posting_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=JournalEntryStatus.choices,
        default=JournalEntryStatus.DRAFT,
        db_index=True
    )
    description = models.TextField()
    source_module = models.CharField(max_length=50)
    source_reference_id = models.CharField(max_length=100, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')

    class Meta:
        ordering = ['-posting_date', '-created_at']

    def __str__(self):
        return f"{self.entry_number} ({self.posting_date}) - {self.status}"

class JournalLine(BaseModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_lines')
    debit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    credit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    client_id = models.UUIDField(null=True, blank=True, db_index=True)
    cost_centre = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    country_code = models.CharField(max_length=2, default='GH', db_index=True)

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("A journal line cannot have both a debit and a credit amount.")
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("A journal line must specify either a debit or credit amount.")
