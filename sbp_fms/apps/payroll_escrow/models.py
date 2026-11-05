from decimal import Decimal
from django.db import models
from apps.common.models import BaseModel
from apps.ledger.models import JournalEntry

class PayrollBatchStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    FUNDING_REQUESTED = 'FUNDING_REQUESTED', 'Funding Invoiced'
    FUNDED = 'FUNDED', 'Escrow Fully Funded'
    DISBURSED = 'DISBURSED', 'Paid Out to Workers & Tax Authorities'
    BLOCKED_SHORTFALL = 'BLOCKED_SHORTFALL', 'Disbursement Blocked (Insufficient Escrow)'

class PayrollBatch(BaseModel):
    batch_code = models.CharField(max_length=50, unique=True)
    client_id = models.UUIDField(db_index=True)
    client_name = models.CharField(max_length=255)
    country_code = models.CharField(max_length=2, default='GH')
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    total_net_salaries = models.DecimalField(max_digits=18, decimal_places=4)
    total_statutory_taxes = models.DecimalField(max_digits=18, decimal_places=4)
    total_management_fee = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=30, choices=PayrollBatchStatus.choices, default=PayrollBatchStatus.DRAFT)
    journal_entry = models.ForeignKey(JournalEntry, null=True, blank=True, on_delete=models.SET_NULL)

    @property
    def total_funding_required(self) -> Decimal:
        return self.total_net_salaries + self.total_statutory_taxes + self.total_management_fee

    def __str__(self):
        return f"{self.batch_code} ({self.client_name}) - Required: {self.total_funding_required} GHS"
