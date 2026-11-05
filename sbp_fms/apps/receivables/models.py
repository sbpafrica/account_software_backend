from decimal import Decimal
from django.db import models
from apps.common.models import BaseModel

class Client(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    country_code = models.CharField(max_length=2, default='GH')
    credit_limit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('50000.0000'))
    payment_terms_days = models.PositiveSmallIntegerField(default=30)

    def __str__(self):
        return f"{self.code} - {self.name}"

class ClientInvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    ISSUED = 'ISSUED', 'Issued to Client'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Fully Paid'
    OVERDUE = 'OVERDUE', 'Overdue'

class ClientInvoice(BaseModel):
    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='invoices')
    issue_date = models.DateField()
    due_date = models.DateField(db_index=True)
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(max_length=20, choices=ClientInvoiceStatus.choices, default=ClientInvoiceStatus.DRAFT)

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.client.name}) - Balance: {self.balance_due}"
