from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key, KEY_AGING_REPORT
from apps.common.filters import apply_dict_filters, merge_filters
from .models import Client, ClientInvoice, ClientInvoiceStatus


def client_list(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> list[Client]:
    combined_filters = merge_filters(filters, country_code=country_code)
    cache_key = make_cache_key('fms:clients:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Client.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def client_detail(*, client_id) -> Client:
    cache_key = f"fms:clients:detail:{client_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    client = get_object_or_404(Client, id=client_id)
    CacheManager.set(cache_key, client, timeout=1800)
    return client


def client_invoice_list(
    *,
    filters: Optional[dict] = None,
    client_id: Optional[str] = None,
    status: Optional[str] = None
) -> list[ClientInvoice]:
    combined_filters = merge_filters(filters, client_id=client_id, status=status)
    cache_key = make_cache_key('fms:receivables:invoices:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = ClientInvoice.objects.select_related('client').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def client_invoice_detail(*, invoice_id) -> ClientInvoice:
    cache_key = f"fms:receivables:invoices:detail:{invoice_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    inv = get_object_or_404(ClientInvoice.objects.select_related('client'), id=invoice_id)
    CacheManager.set(cache_key, inv, timeout=1800)
    return inv


def aging_report_get(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> dict:
    combined_filters = merge_filters(filters, country_code=country_code)
    target_country = combined_filters.get('country_code') or country_code or 'ALL'
    cache_key = KEY_AGING_REPORT.format(country=target_country)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    today = timezone.now().date()
    invoices = ClientInvoice.objects.filter(
        status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID, ClientInvoiceStatus.OVERDUE]
    )
    if target_country and target_country != 'ALL':
        invoices = invoices.filter(client__country_code=target_country)

    buckets = {
        'country_code': target_country,
        'current_0_30_days': Decimal('0'),
        'overdue_31_60_days': Decimal('0'),
        'overdue_61_90_days': Decimal('0'),
        'overdue_90_plus_days': Decimal('0'),
        'total_receivables': Decimal('0')
    }

    for inv in invoices:
        bal = inv.balance_due
        days_overdue = (today - inv.due_date).days
        buckets['total_receivables'] += bal

        if days_overdue <= 30:
            buckets['current_0_30_days'] += bal
        elif 31 <= days_overdue <= 60:
            buckets['overdue_31_60_days'] += bal
        elif 61 <= days_overdue <= 90:
            buckets['overdue_61_90_days'] += bal
        else:
            buckets['overdue_90_plus_days'] += bal

    CacheManager.set(cache_key, buckets, timeout=1800)
    return buckets
