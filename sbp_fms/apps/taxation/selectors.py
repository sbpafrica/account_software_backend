from typing import Optional
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from .models import TaxRule


def tax_rule_list(*, filters: Optional[dict] = None, country_code: Optional[str] = None, tax_type: Optional[str] = None) -> list[TaxRule]:
    combined_filters = merge_filters(filters, country_code=country_code, tax_type=tax_type)
    cache_key = make_cache_key('fms:tax:rules:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = TaxRule.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def tax_rule_detail(*, rule_id) -> TaxRule:
    cache_key = f"fms:tax:rules:detail:{rule_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    rule = get_object_or_404(TaxRule, id=rule_id)
    CacheManager.set(cache_key, rule, timeout=1800)
    return rule
