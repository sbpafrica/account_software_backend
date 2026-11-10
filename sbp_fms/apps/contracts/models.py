from decimal import Decimal
from django.db import models
from apps.common.models import BaseModel


class ContractStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    TERMINATED = 'TERMINATED', 'Terminated'


class Contract(BaseModel):
    contract_number = models.CharField(max_length=50, unique=True, db_index=True)
    client = models.ForeignKey('receivables.Client', on_delete=models.PROTECT, related_name='contracts')
    title = models.CharField(max_length=255)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True)
    total_contract_value = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.ACTIVE, db_index=True)
    cost_centre = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-start_date', 'contract_number']

    def __str__(self):
        return f"{self.contract_number} - {self.client.name}: {self.title} ({self.status})"
