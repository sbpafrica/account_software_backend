from decimal import Decimal
from django.db import models
from apps.common.models import BaseModel
from apps.ledger.models import Account

class BankAccount(BaseModel):
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, unique=True)
    currency = models.CharField(max_length=3, default='GHS')
    country_code = models.CharField(max_length=2, default='GH')
    gl_account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name='bank_account')

    def __str__(self):
        return f"{self.bank_name} - {self.account_number} ({self.currency})"

class BankTransaction(BaseModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_date = models.DateField(db_index=True)
    bank_reference = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    is_reconciled = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.bank_reference} ({self.amount}) - Reconciled: {self.is_reconciled}"
