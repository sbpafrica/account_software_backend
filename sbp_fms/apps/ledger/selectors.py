from decimal import Decimal
from typing import Optional
from django import db
from django.db import models
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key, KEY_TRIAL_BALANCE, KEY_ACCOUNTS_LIST
from apps.common.filters import apply_dict_filters, merge_filters
from .models import Account, JournalEntry, JournalLine, JournalEntryStatus


def account_list(
    *,
    filters: Optional[dict] = None,
    country_code: Optional[str] = None,
    account_type: Optional[str] = None,
    is_active: bool = True
) -> list[Account]:
    combined_filters = merge_filters(
        filters,
        country_code=country_code,
        account_type=account_type,
        is_active=is_active
    )
    cache_key = make_cache_key('fms:accounts:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Account.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=3600)
    return results


def account_detail(*, account_id) -> Account:
    cache_key = f"fms:accounts:detail:{account_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    acct = get_object_or_404(Account, id=account_id)
    CacheManager.set(cache_key, acct, timeout=3600)
    return acct


def journal_entry_list(
    *,
    filters: Optional[dict] = None,
    status: Optional[str] = None,
    source_module: Optional[str] = None,
    date_from=None,
    date_to=None
) -> list[JournalEntry]:
    combined_filters = merge_filters(
        filters,
        status=status,
        source_module=source_module,
        posting_date__gte=date_from,
        posting_date__lte=date_to
    )
    cache_key = make_cache_key('fms:journals:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = JournalEntry.objects.select_related('created_by', 'approved_by').prefetch_related('lines__account').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def journal_entry_detail(*, entry_id) -> JournalEntry:
    cache_key = f"fms:journals:detail:{entry_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    entry = get_object_or_404(
        JournalEntry.objects.select_related('created_by', 'approved_by').prefetch_related('lines__account'),
        id=entry_id
    )
    CacheManager.set(cache_key, entry, timeout=1800)
    return entry


def trial_balance_get(*, filters: Optional[dict] = None, as_of_date=None, country_code=None) -> dict:
    combined_filters = merge_filters(filters, as_of_date=as_of_date, country_code=country_code)
    target_date = combined_filters.get('as_of_date') or as_of_date
    target_country = combined_filters.get('country_code') or country_code or 'ALL'

    cache_key = KEY_TRIAL_BALANCE.format(country=target_country, date=target_date)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = JournalLine.objects.filter(entry__status=JournalEntryStatus.POSTED)
    if target_date:
        qs = qs.filter(entry__posting_date__lte=target_date)
    if target_country and target_country != 'ALL':
        qs = qs.filter(country_code=target_country)

    accounts_data = []
    total_debits = Decimal('0')
    total_credits = Decimal('0')

    for account in Account.objects.filter(is_active=True):
        agg = qs.filter(account=account).aggregate(
            sum_debit=models.Sum('debit'),
            sum_credit=models.Sum('credit')
        )
        d = agg['sum_debit'] or Decimal('0')
        c = agg['sum_credit'] or Decimal('0')
        if d > 0 or c > 0:
            accounts_data.append({
                'account_id': str(account.id),
                'account_code': account.code,
                'account_name': account.name,
                'account_type': account.account_type,
                'total_debit': d,
                'total_credit': c,
                'net_balance': d - c
            })
            total_debits += d
            total_credits += c

    result = {
        'as_of_date': str(target_date),
        'country_code': target_country,
        'grand_total_debits': total_debits,
        'grand_total_credits': total_credits,
        'is_balanced': total_debits == total_credits,
        'accounts': accounts_data,
    }
    CacheManager.set(cache_key, result, timeout=1800)
    return result
