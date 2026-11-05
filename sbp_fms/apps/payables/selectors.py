from typing import Optional
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from .models import Supplier, SupplierInvoice


def supplier_list(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> list[Supplier]:
    combined_filters = merge_filters(filters, country_code=country_code)
    cache_key = make_cache_key('fms:suppliers:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Supplier.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def supplier_detail(*, supplier_id) -> Supplier:
    cache_key = f"fms:suppliers:detail:{supplier_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    supplier = get_object_or_404(Supplier, id=supplier_id)
    CacheManager.set(cache_key, supplier, timeout=1800)
    return supplier


def supplier_invoice_list(
    *,
    filters: Optional[dict] = None,
    match_status: Optional[str] = None,
    supplier_id: Optional[str] = None
) -> list[SupplierInvoice]:
    combined_filters = merge_filters(filters, match_status=match_status, supplier_id=supplier_id)
    cache_key = make_cache_key('fms:payables:invoices:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = SupplierInvoice.objects.select_related('supplier', 'po', 'grn').prefetch_related('lines').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def supplier_invoice_detail(*, invoice_id) -> SupplierInvoice:
    cache_key = f"fms:payables:invoices:detail:{invoice_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    inv = get_object_or_404(
        SupplierInvoice.objects.select_related('supplier', 'po', 'grn').prefetch_related('lines'),
        id=invoice_id
    )
    CacheManager.set(cache_key, inv, timeout=1800)
    return inv
