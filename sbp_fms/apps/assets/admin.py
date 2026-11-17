from django.contrib import admin
from apps.assets.models import AssetCategory, FixedAsset, DepreciationRun, DepreciationScheduleLine


class DepreciationScheduleLineInline(admin.TabularInline):
    model = DepreciationScheduleLine
    extra = 0
    readonly_fields = ('period_date', 'depreciation_amount', 'accumulated_before', 'accumulated_after', 'book_value_after')


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'default_useful_life_years', 'default_depreciation_method', 'country_code', 'created_at')
    list_filter = ('default_depreciation_method', 'country_code')
    search_fields = ('name', 'code')


@admin.register(FixedAsset)
class FixedAssetAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'name', 'category', 'purchase_date', 'purchase_cost', 'net_book_value', 'status', 'country_code')
    list_filter = ('status', 'category', 'country_code')
    search_fields = ('asset_tag', 'name')
    inlines = [DepreciationScheduleLineInline]


@admin.register(DepreciationRun)
class DepreciationRunAdmin(admin.ModelAdmin):
    list_display = ('run_number', 'period_end_date', 'total_depreciation', 'total_assets_processed', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('run_number',)
