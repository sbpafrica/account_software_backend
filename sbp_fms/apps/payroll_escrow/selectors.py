from decimal import Decimal
from typing import Optional
from django.db import models
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key, KEY_CLIENT_ESCROW
from apps.common.filters import apply_dict_filters, merge_filters
from apps.ledger.models import Account, JournalEntryStatus
from .models import PayrollBatch


def payroll_batch_list(
    *,
    filters: Optional[dict] = None,
    country_code: Optional[str] = None,
    status: Optional[str] = None,
    client_id: Optional[str] = None
) -> list[PayrollBatch]:
    combined_filters = merge_filters(
        filters,
        country_code=country_code,
        status=status,
        client_id=client_id
    )
    cache_key = make_cache_key('fms:payroll:batches:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = PayrollBatch.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def payroll_batch_detail(*, batch_id) -> PayrollBatch:
    cache_key = f"fms:payroll:batches:detail:{batch_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    batch = get_object_or_404(PayrollBatch, id=batch_id)
    CacheManager.set(cache_key, batch, timeout=1800)
    return batch


def client_escrow_balance_get(*, client_id, country_code='GH') -> Decimal:
    cache_key = KEY_CLIENT_ESCROW.format(client_id=client_id, country=country_code)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    escrow_account = Account.objects.filter(code__startswith='2100', country_code=country_code).first()
    if not escrow_account:
        return Decimal('0')

    agg = escrow_account.journal_lines.filter(
        entry__status=JournalEntryStatus.POSTED,
        client_id=client_id
    ).aggregate(
        tot_cred=models.Sum('credit'),
        tot_deb=models.Sum('debit')
    )
    balance = (agg['tot_cred'] or Decimal('0')) - (agg['tot_deb'] or Decimal('0'))
    CacheManager.set(cache_key, balance, timeout=1800)
    return balance
