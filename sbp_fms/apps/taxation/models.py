from decimal import Decimal
from django.db import models
from apps.common.models import BaseModel

class TaxType(models.TextChoices):
    PAYE = 'PAYE', 'Personal Income Tax (PAYE)'
    SSNIT = 'SSNIT', 'Social Security / Pension'
    WHT = 'WHT', 'Withholding Tax'
    VAT = 'VAT', 'Value Added Tax'

class TaxRule(BaseModel):
    country_code = models.CharField(max_length=2, db_index=True)
    tax_type = models.CharField(max_length=20, choices=TaxType.choices)
    bracket_min = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    bracket_max = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    effective_from = models.DateField()

    def __str__(self):
        return f"{self.country_code} - {self.tax_type}: {self.rate * 100}%"
