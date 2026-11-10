from decimal import Decimal
from typing import Optional
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key, KEY_CASH_FORECAST
from apps.common.filters import apply_dict_filters, merge_filters
from apps.receivables.models import ClientInvoice, ClientInvoiceStatus
from apps.payables.models import SupplierInvoice, MatchStatus
from .models import BankAccount, BankTransaction


def bank_account_list(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> list[BankAccount]:
    combined_filters = merge_filters(filters, country_code=country_code)
    cache_key = make_cache_key('fms:treasury:accounts:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = BankAccount.objects.select_related('gl_account').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def bank_account_detail(*, account_id) -> BankAccount:
    cache_key = f"fms:treasury:accounts:detail:{account_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    account = get_object_or_404(BankAccount.objects.select_related('gl_account'), id=account_id)
    CacheManager.set(cache_key, account, timeout=1800)
    return account


def bank_transaction_list(
    *,
    filters: Optional[dict] = None,
    bank_account_id: Optional[str] = None,
    is_reconciled: Optional[bool] = None
) -> list[BankTransaction]:
    combined_filters = merge_filters(filters, bank_account_id=bank_account_id, is_reconciled=is_reconciled)
    cache_key = make_cache_key('fms:treasury:transactions:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = BankTransaction.objects.select_related('bank_account').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def bank_transaction_detail(*, transaction_id) -> BankTransaction:
    cache_key = f"fms:treasury:transactions:detail:{transaction_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    tx = get_object_or_404(BankTransaction.objects.select_related('bank_account'), id=transaction_id)
    CacheManager.set(cache_key, tx, timeout=1800)
    return tx


def liquidity_forecast_get() -> dict:
    cached = CacheManager.get(KEY_CASH_FORECAST)
    if cached is not None:
        return cached

    current_cash = Decimal('1500000.0000')
    today = timezone.now().date()
    w30, w60, w90 = today + timedelta(days=30), today + timedelta(days=60), today + timedelta(days=90)

    ar_30 = sum(inv.balance_due for inv in ClientInvoice.objects.filter(due_date__lte=w30, status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID]))
    ar_60 = sum(inv.balance_due for inv in ClientInvoice.objects.filter(due_date__lte=w60, status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID]))
    ar_90 = sum(inv.balance_due for inv in ClientInvoice.objects.filter(due_date__lte=w90, status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID]))
    ap_pending = sum(inv.net_payable_amount for inv in SupplierInvoice.objects.filter(match_status=MatchStatus.MATCHED))

    forecast = {
        'current_available_cash': current_cash,
        'forecast_30_days': current_cash + ar_30 - ap_pending,
        'forecast_60_days': current_cash + ar_60 - ap_pending,
        'forecast_90_days': current_cash + ar_90 - ap_pending,
        'pending_supplier_payables': ap_pending,
    }
    CacheManager.set(KEY_CASH_FORECAST, forecast, timeout=1800)
    return forecast
