from typing import Optional
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from .models import Supplier, SupplierInvoice, PurchaseOrder, GoodsReceivedNote


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


def purchase_order_list(*, filters: Optional[dict] = None, supplier_id: Optional[str] = None) -> list[PurchaseOrder]:
    combined_filters = merge_filters(filters, supplier_id=supplier_id)
    cache_key = make_cache_key('fms:payables:po:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = PurchaseOrder.objects.select_related('supplier').prefetch_related('lines').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def purchase_order_detail(*, po_id) -> PurchaseOrder:
    cache_key = f"fms:payables:po:detail:{po_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    po = get_object_or_404(PurchaseOrder.objects.select_related('supplier').prefetch_related('lines'), id=po_id)
    CacheManager.set(cache_key, po, timeout=1800)
    return po


def goods_received_note_list(*, filters: Optional[dict] = None, po_id: Optional[str] = None) -> list[GoodsReceivedNote]:
    combined_filters = merge_filters(filters, po_id=po_id)
    cache_key = make_cache_key('fms:payables:grn:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = GoodsReceivedNote.objects.select_related('po').prefetch_related('lines').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def goods_received_note_detail(*, grn_id) -> GoodsReceivedNote:
    cache_key = f"fms:payables:grn:detail:{grn_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    grn = get_object_or_404(GoodsReceivedNote.objects.select_related('po').prefetch_related('lines'), id=grn_id)
    CacheManager.set(cache_key, grn, timeout=1800)
    return grn


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
