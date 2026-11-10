from django.urls import path
from apps.assets.api.admin import (
    AssetCategoryListCreateAdminApi, AssetCategoryDetailAdminApi,
    FixedAssetListCreateAdminApi, FixedAssetDetailAdminApi,
    FixedAssetScheduleAdminApi, FixedAssetDisposeAdminApi,
    DepreciationRunListCalculateAdminApi, DepreciationRunDetailAdminApi,
    DepreciationRunPostAdminApi, AssetRegisterSummaryAdminApi
)

urlpatterns = [
    # Asset Categories
    path('admin/categories/', AssetCategoryListCreateAdminApi.as_view(), name='asset-category-list-create-admin'),
    path('admin/categories/<uuid:category_id>/', AssetCategoryDetailAdminApi.as_view(), name='asset-category-detail-admin'),

    # Fixed Assets Register
    path('admin/assets/', FixedAssetListCreateAdminApi.as_view(), name='fixed-asset-list-create-admin'),
    path('admin/assets/<uuid:asset_id>/', FixedAssetDetailAdminApi.as_view(), name='fixed-asset-detail-admin'),
    path('admin/assets/<uuid:asset_id>/schedule/', FixedAssetScheduleAdminApi.as_view(), name='fixed-asset-schedule-admin'),
    path('admin/assets/<uuid:asset_id>/dispose/', FixedAssetDisposeAdminApi.as_view(), name='fixed-asset-dispose-admin'),

    # Depreciation Runs
    path('admin/depreciation-runs/', DepreciationRunListCalculateAdminApi.as_view(), name='depreciation-run-list-calculate-admin'),
    path('admin/depreciation-runs/<uuid:run_id>/', DepreciationRunDetailAdminApi.as_view(), name='depreciation-run-detail-admin'),
    path('admin/depreciation-runs/<uuid:run_id>/post/', DepreciationRunPostAdminApi.as_view(), name='depreciation-run-post-admin'),

    # Financial Summary
    path('admin/summary/', AssetRegisterSummaryAdminApi.as_view(), name='asset-register-summary-admin'),
]
