from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import BaseModel
from apps.ledger.models import Account


class DepreciationMethod(models.TextChoices):
    STRAIGHT_LINE = 'STRAIGHT_LINE', 'Straight Line'
    REDUCING_BALANCE = 'REDUCING_BALANCE', 'Reducing Balance'


class AssetStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active in Service'
    DISPOSED = 'DISPOSED', 'Disposed / Sold / Scrapped'
    FULLY_DEPRECIATED = 'FULLY_DEPRECIATED', 'Fully Depreciated'


class AssetCategory(BaseModel):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    default_useful_life_years = models.PositiveIntegerField(default=5)
    default_depreciation_method = models.CharField(
        max_length=30,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.STRAIGHT_LINE
    )
    asset_gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='+')
    accumulated_depr_gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='+')
    depr_expense_gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='+')
    country_code = models.CharField(max_length=2, default='GH')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class FixedAsset(BaseModel):
    asset_tag = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets')
    purchase_date = models.DateField(db_index=True)
    purchase_cost = models.DecimalField(max_digits=18, decimal_places=4)
    salvage_value = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    useful_life_years = models.PositiveIntegerField(default=5)
    depreciation_method = models.CharField(
        max_length=30,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.STRAIGHT_LINE
    )
    depreciation_rate_pct = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    net_book_value = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(
        max_length=20,
        choices=AssetStatus.choices,
        default=AssetStatus.ACTIVE,
        db_index=True
    )
    department = models.CharField(max_length=100, blank=True, default='')
    cost_centre = models.CharField(max_length=100, blank=True, default='')
    location = models.CharField(max_length=255, blank=True, default='')
    disposal_date = models.DateField(null=True, blank=True)
    disposal_proceeds = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    disposal_gain_loss = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    country_code = models.CharField(max_length=2, default='GH')

    class Meta:
        ordering = ['-purchase_date', 'asset_tag']

    def __str__(self):
        return f"{self.asset_tag} - {self.name} (NBV: {self.net_book_value})"


class DepreciationRunStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    POSTED = 'POSTED', 'Posted'


class DepreciationRun(BaseModel):
    run_number = models.CharField(max_length=50, unique=True, db_index=True)
    period_end_date = models.DateField(db_index=True)
    total_depreciation = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    total_assets_processed = models.PositiveIntegerField(default=0)
    journal_entry = models.ForeignKey('ledger.JournalEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    status = models.CharField(
        max_length=20,
        choices=DepreciationRunStatus.choices,
        default=DepreciationRunStatus.DRAFT,
        db_index=True
    )
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-period_end_date', '-created_at']

    def __str__(self):
        return f"{self.run_number} ({self.period_end_date}) - {self.status}"


class DepreciationScheduleLine(BaseModel):
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name='depreciation_lines')
    depreciation_run = models.ForeignKey(DepreciationRun, null=True, blank=True, on_delete=models.SET_NULL, related_name='schedule_lines')
    period_date = models.DateField(db_index=True)
    depreciation_amount = models.DecimalField(max_digits=18, decimal_places=4)
    accumulated_before = models.DecimalField(max_digits=18, decimal_places=4)
    accumulated_after = models.DecimalField(max_digits=18, decimal_places=4)
    book_value_after = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ['asset', 'period_date']

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.period_date}: {self.depreciation_amount}"
