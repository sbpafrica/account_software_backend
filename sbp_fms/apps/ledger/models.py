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
    OPEX = 'OPEX', 'Operating Expense (6000-7999)'

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
    ACCOUNT_CODE_RANGES = {
        AccountType.ASSET: (1000, 1999),
        AccountType.LIABILITY: (2000, 2999),
        AccountType.EQUITY: (3000, 3999),
        AccountType.REVENUE: (4000, 4999),
        AccountType.DIRECT_COST: (5000, 5999),
        AccountType.OPEX: (6000, 7999),
    }

    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Leave blank to automatically generate code based on Account Type."
    )
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

    @classmethod
    def generate_next_code(cls, account_type: str) -> str:
        """
        Automatically generates the next sequential account code adhering to the standard IFRS/GAAP COA structure:
          - 1000 - 1999: Assets (Current, Non-Current, Bank, Accounts Receivable)
          - 2000 - 2999: Liabilities (Current, Accounts Payable, Accruals, Tax Liabilities)
          - 3000 - 3999: Equity (Share Capital, Retained Earnings, Currency Translation Reserve)
          - 4000 - 4999: Revenue (Service Fees, Management Fees, Reimbursable Revenue)
          - 5000 - 5999: Cost of Sales / Direct Workforce Costs (Direct Salaries, Statutory Social Security)
          - 6000 - 7999: Operating Expenses (Rent, Utilities, IT, Depreciation)
        """
        import re
        min_code, max_code = cls.ACCOUNT_CODE_RANGES.get(account_type, (1000, 1999))

        existing_codes = list(cls.objects.values_list('code', flat=True))
        used_numbers = set()
        for c in existing_codes:
            m = re.match(r'^(\d{4})', str(c).strip())
            if m:
                used_numbers.add(int(m.group(1)))

        # Standard accounting codes increment by 10 (e.g. 1010, 1020, 1030...)
        candidate = min_code + 10
        while candidate <= max_code:
            if candidate not in used_numbers and str(candidate) not in existing_codes:
                return str(candidate)
            candidate += 10

        # Fallback to single increments (e.g. 1001, 1002...) if multiples of 10 are filled
        candidate = min_code + 1
        while candidate <= max_code:
            if candidate not in used_numbers and str(candidate) not in existing_codes:
                return str(candidate)
            candidate += 1

        raise ValidationError(f"All account codes in range {min_code} - {max_code} for {account_type} are in use.")

    def save(self, *args, **kwargs):
        if not self.code or not str(self.code).strip():
            self.code = self.generate_next_code(self.account_type)
        else:
            self.code = str(self.code).strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.currency})"

class JournalEntryStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    POSTED = 'POSTED', 'Posted'
    REVERSED = 'REVERSED', 'Reversed'

class JournalEntry(TenantModel):
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
