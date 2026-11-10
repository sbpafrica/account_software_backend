from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import BaseModel


class BudgetStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted for Review'
    APPROVED = 'APPROVED', 'Approved & Active'
    CLOSED = 'CLOSED', 'Closed'


class Budget(BaseModel):
    name = models.CharField(max_length=150)
    financial_year = models.PositiveIntegerField(db_index=True)
    department = models.CharField(max_length=100, blank=True, default='')
    cost_centre = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=20, choices=BudgetStatus.choices, default=BudgetStatus.DRAFT, db_index=True)
    total_budget = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-financial_year', 'name']

    def __str__(self):
        return f"{self.name} ({self.financial_year}) - Status: {self.status}"


class BudgetLine(BaseModel):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey('ledger.Account', on_delete=models.PROTECT, related_name='+')
    period_month = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-12 or None for annual
    planned_amount = models.DecimalField(max_digits=18, decimal_places=4)
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['budget', 'account', 'period_month']

    def __str__(self):
        return f"{self.budget.name}: {self.account.code} - Planned: {self.planned_amount}"
