from decimal import Decimal
from rest_framework import serializers
from .models import (
    AssetCategory, FixedAsset, DepreciationRun,
    DepreciationScheduleLine
)


class AssetCategoryOutputSerializer(serializers.ModelSerializer):
    asset_gl_code = serializers.CharField(source='asset_gl_account.code', read_only=True)
    accumulated_depr_gl_code = serializers.CharField(source='accumulated_depr_gl_account.code', read_only=True)
    depr_expense_gl_code = serializers.CharField(source='depr_expense_gl_account.code', read_only=True)

    class Meta:
        model = AssetCategory
        fields = '__all__'


class AssetCategoryCreateInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=100)
    default_useful_life_years = serializers.IntegerField(default=5, required=False)
    default_depreciation_method = serializers.CharField(max_length=30, default='STRAIGHT_LINE', required=False)
    asset_gl_account_id = serializers.UUIDField()
    accumulated_depr_gl_account_id = serializers.UUIDField()
    depr_expense_gl_account_id = serializers.UUIDField()
    country_code = serializers.CharField(max_length=2, default='GH', required=False)


class AssetCategoryUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    default_useful_life_years = serializers.IntegerField(required=False)
    default_depreciation_method = serializers.CharField(max_length=30, required=False)


class FixedAssetOutputSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)

    class Meta:
        model = FixedAsset
        fields = '__all__'


class FixedAssetCreateInputSerializer(serializers.Serializer):
    asset_tag = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    category_id = serializers.UUIDField()
    purchase_date = serializers.DateField()
    purchase_cost = serializers.DecimalField(max_digits=18, decimal_places=4)
    salvage_value = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'), required=False)
    useful_life_years = serializers.IntegerField(required=False, allow_null=True)
    depreciation_method = serializers.CharField(max_length=30, required=False, allow_blank=True)
    depreciation_rate_pct = serializers.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'), required=False)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    cost_centre = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    location = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    country_code = serializers.CharField(max_length=2, default='GH', required=False)


class FixedAssetUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    cost_centre = serializers.CharField(max_length=100, required=False, allow_blank=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)


class FixedAssetDisposeInputSerializer(serializers.Serializer):
    disposal_date = serializers.DateField()
    sale_proceeds = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    bank_account_id = serializers.UUIDField(required=False, allow_null=True)
    gain_loss_account_id = serializers.UUIDField(required=False, allow_null=True)


class DepreciationScheduleLineOutputSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)

    class Meta:
        model = DepreciationScheduleLine
        fields = '__all__'


class DepreciationRunOutputSerializer(serializers.ModelSerializer):
    schedule_lines = DepreciationScheduleLineOutputSerializer(many=True, read_only=True)
    journal_entry_number = serializers.CharField(source='journal_entry.entry_number', read_only=True)

    class Meta:
        model = DepreciationRun
        fields = '__all__'


class DepreciationRunCalculateInputSerializer(serializers.Serializer):
    period_end_date = serializers.DateField()


class AssetRegisterSummaryOutputSerializer(serializers.Serializer):
    total_asset_count = serializers.IntegerField()
    active_asset_count = serializers.IntegerField()
    total_acquisition_cost = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_accumulated_depreciation = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_net_book_value = serializers.DecimalField(max_digits=18, decimal_places=4)
