from decimal import Decimal
from typing import Optional
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404

from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from .models import (
    AssetCategory, FixedAsset, AssetStatus,
    DepreciationRun, DepreciationScheduleLine
)


def asset_category_list(*, country_code: Optional[str] = None) -> list[AssetCategory]:
    cache_key = make_cache_key("fms:assets:categories", country_code=country_code)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = AssetCategory.objects.select_related(
        'asset_gl_account', 'accumulated_depr_gl_account', 'depr_expense_gl_account'
    ).all()
    if country_code:
        qs = qs.filter(country_code=country_code)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def asset_category_detail(*, category_id) -> AssetCategory:
    cache_key = make_cache_key("fms:assets:category", identifier=category_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    category = get_object_or_404(
        AssetCategory.objects.select_related(
            'asset_gl_account', 'accumulated_depr_gl_account', 'depr_expense_gl_account'
        ),
        id=category_id
    )
    CacheManager.set(cache_key, category, timeout=1800)
    return category


def fixed_asset_list(
    *,
    filters: Optional[dict] = None,
    category_id: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    country_code: Optional[str] = None
) -> list[FixedAsset]:
    combined_filters = merge_filters(
        filters,
        category_id=category_id,
        status=status,
        department=department,
        country_code=country_code
    )
    cache_key = make_cache_key("fms:assets:list", filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = FixedAsset.objects.select_related('category').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def fixed_asset_detail(*, asset_id) -> FixedAsset:
    cache_key = make_cache_key("fms:assets:detail", identifier=asset_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    asset = get_object_or_404(
        FixedAsset.objects.select_related('category').prefetch_related('depreciation_lines'),
        id=asset_id
    )
    CacheManager.set(cache_key, asset, timeout=1800)
    return asset


def depreciation_run_list() -> list[DepreciationRun]:
    cache_key = make_cache_key("fms:depr:runs")
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    runs = list(DepreciationRun.objects.select_related('journal_entry', 'run_by').all())
    CacheManager.set(cache_key, runs, timeout=1800)
    return runs


def depreciation_run_detail(*, run_id) -> DepreciationRun:
    cache_key = make_cache_key("fms:depr:run", identifier=run_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    run = get_object_or_404(
        DepreciationRun.objects.select_related('journal_entry', 'run_by').prefetch_related('schedule_lines__asset'),
        id=run_id
    )
    CacheManager.set(cache_key, run, timeout=1800)
    return run


def fixed_asset_schedule_get(*, asset_id) -> list[DepreciationScheduleLine]:
    cache_key = make_cache_key("fms:assets:schedule", identifier=asset_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    schedule = list(DepreciationScheduleLine.objects.filter(asset_id=asset_id).order_by('period_date'))
    CacheManager.set(cache_key, schedule, timeout=1800)
    return schedule


def asset_register_summary_get(*, country_code: Optional[str] = None) -> dict:
    cache_key = make_cache_key("fms:assets:summary", country_code=country_code)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = FixedAsset.objects.all()
    if country_code:
        qs = qs.filter(country_code=country_code)

    agg = qs.aggregate(
        total_assets=Count('id'),
        active_assets=Count('id', filter=Q(status=AssetStatus.ACTIVE)),
        total_cost=Sum('purchase_cost'),
        total_accum_depr=Sum('accumulated_depreciation'),
        total_nbv=Sum('net_book_value')
    )
    result = {
        'total_asset_count': agg['total_assets'] or 0,
        'active_asset_count': agg['active_assets'] or 0,
        'total_acquisition_cost': agg['total_cost'] or Decimal('0.0000'),
        'total_accumulated_depreciation': agg['total_accum_depr'] or Decimal('0.0000'),
        'total_net_book_value': agg['total_nbv'] or Decimal('0.0000'),
    }
    CacheManager.set(cache_key, result, timeout=1800)
    return result
