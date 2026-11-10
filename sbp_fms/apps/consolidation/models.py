from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import BaseModel


class RateType(models.TextChoices):
    CLOSING = 'CLOSING', 'Month-End Closing Rate'
    AVERAGE = 'AVERAGE', 'Period Average Rate'
    SPOT = 'SPOT', 'Spot Transaction Rate'


class ExchangeRate(BaseModel):
    from_currency = models.CharField(max_length=3, db_index=True)  # e.g. USD, EUR, GBP
    to_currency = models.CharField(max_length=3, db_index=True, default='GHS')  # Reporting/Base currency
    rate_date = models.DateField(db_index=True)
    rate = models.DecimalField(max_digits=18, decimal_places=6)  # e.g. 15.500000 GHS per 1 USD
    rate_type = models.CharField(max_length=20, choices=RateType.choices, default=RateType.CLOSING)

    class Meta:
        ordering = ['-rate_date', 'from_currency', 'to_currency']
        unique_together = ('from_currency', 'to_currency', 'rate_date', 'rate_type')

    def __str__(self):
        return f"{self.rate_date}: 1 {self.from_currency} = {self.rate} {self.to_currency} ({self.rate_type})"


class FXRevaluationRun(BaseModel):
    revaluation_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=3, default='GHS')
    total_gain_loss = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    journal_entry = models.ForeignKey(
        'ledger.JournalEntry',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='fx_revaluations'
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-revaluation_date', '-created_at']

    def __str__(self):
        return f"FX Revaluation {self.revaluation_date} ({self.reporting_currency}) - Gain/Loss: {self.total_gain_loss}"
