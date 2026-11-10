from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q
from apps.common.cache import CacheManager, make_cache_key
from apps.ledger.models import Account, AccountType, JournalLine
from .models import ExchangeRate, FXRevaluationRun, RateType


def exchange_rate_list(*, from_currency: str = None, to_currency: str = None, rate_date=None):
    cache_key = make_cache_key("fms:fx:rates", from_currency=from_currency, to_currency=to_currency, rate_date=rate_date)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = ExchangeRate.objects.all()
    if from_currency:
        qs = qs.filter(from_currency=from_currency.upper())
    if to_currency:
        qs = qs.filter(to_currency=to_currency.upper())
    if rate_date:
        qs = qs.filter(rate_date=rate_date)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=3600)
    return results


def exchange_rate_get_latest(*, from_currency: str, to_currency: str = 'GHS', as_of_date=None) -> Decimal:
    """
    Returns the exchange rate to convert 1 unit of `from_currency` into `to_currency`.
    If from_currency == to_currency, returns Decimal('1.000000').
    Fetches real-time spot rates from online (Groq AI / XE.com), cached with short TTL (few minutes).
    """
    from_curr = from_currency.upper()
    to_curr = to_currency.upper()

    if from_curr == to_curr:
        return Decimal('1.000000')

    parsed_date = None
    if as_of_date:
        if isinstance(as_of_date, str):
            try:
                from datetime import datetime as dt
                parsed_date = dt.strptime(as_of_date, '%Y-%m-%d').date()
            except Exception:
                pass
        elif hasattr(as_of_date, 'year'):
            parsed_date = as_of_date

    cache_key = make_cache_key("fms:fx:latest", from_curr=from_curr, to_curr=to_curr, as_of=str(parsed_date) if parsed_date else 'latest')
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    # 1. Check if an explicit rate was configured in DB
    qs = ExchangeRate.objects.filter(from_currency=from_curr, to_currency=to_curr)
    if parsed_date:
        qs = qs.filter(rate_date__lte=parsed_date)
    rate_obj = qs.order_by('-rate_date').first()

    if rate_obj:
        val = rate_obj.rate
        CacheManager.set(cache_key, val, timeout=600)
        return val

    # 2. Check inverse rate in DB
    inv_qs = ExchangeRate.objects.filter(from_currency=to_curr, to_currency=from_curr)
    if parsed_date:
        inv_qs = inv_qs.filter(rate_date__lte=parsed_date)
    inv_rate = inv_qs.order_by('-rate_date').first()
    if inv_rate and inv_rate.rate > 0:
        val = (Decimal('1.000000') / inv_rate.rate).quantize(Decimal('0.000001'))
        CacheManager.set(cache_key, val, timeout=600)
        return val

    # 3. If no explicit rate is stored or converting live spot rates: fetch live via Groq AI
    try:
        from .groq_fx import GroqExchangeRateService
        live_data = GroqExchangeRateService.fetch_live_rate(from_currency=from_curr, to_currency=to_curr)
        val = live_data['rate']
        CacheManager.set(cache_key, val, timeout=600)
        return val
    except Exception:
        pass

    fallback = Decimal('1.000000')
    CacheManager.set(cache_key, fallback, timeout=600)
    return fallback


def fx_revaluation_run_list():
    cache_key = make_cache_key("fms:fx:runs")
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    runs = list(FXRevaluationRun.objects.select_related('journal_entry', 'created_by').all())
    CacheManager.set(cache_key, runs, timeout=1800)
    return runs


def consolidated_trial_balance_get(*, as_of_date=None, reporting_currency: str = 'GHS'):
    """
    Produces a multi-entity consolidated Trial Balance converted into the chosen reporting currency.
    Translates monetary and non-monetary balances using current exchange rates.
    """
    rep_curr = reporting_currency.upper()
    cache_key = make_cache_key("fms:fx:consolidated_tb", as_of=str(as_of_date) if as_of_date else 'latest', rep_curr=rep_curr)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    accounts = Account.objects.filter(is_active=True).order_by('code')
    lines_qs = JournalLine.objects.filter(entry__status='POSTED')
    if as_of_date:
        lines_qs = lines_qs.filter(entry__posting_date__lte=as_of_date)

    items = []
    total_consolidated_debit = Decimal('0.0000')
    total_consolidated_credit = Decimal('0.0000')

    for acct in accounts:
        acct_lines = lines_qs.filter(account=acct)
        totals = acct_lines.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )
        orig_debit = totals['total_debit'] or Decimal('0.0000')
        orig_credit = totals['total_credit'] or Decimal('0.0000')

        if orig_debit == 0 and orig_credit == 0:
            continue

        orig_currency = acct.currency.upper() if acct.currency else 'GHS'
        fx_rate = exchange_rate_get_latest(from_currency=orig_currency, to_currency=rep_curr, as_of_date=as_of_date)

        cons_debit = (orig_debit * fx_rate).quantize(Decimal('0.0001'))
        cons_credit = (orig_credit * fx_rate).quantize(Decimal('0.0001'))

        total_consolidated_debit += cons_debit
        total_consolidated_credit += cons_credit

        items.append({
            'account_id': str(acct.id),
            'account_code': acct.code,
            'account_name': acct.name,
            'account_type': acct.account_type,
            'original_currency': orig_currency,
            'original_debit': orig_debit,
            'original_credit': orig_credit,
            'exchange_rate': fx_rate,
            'consolidated_debit': cons_debit,
            'consolidated_credit': cons_credit
        })

    imbalance = (total_consolidated_debit - total_consolidated_credit).quantize(Decimal('0.0001'))

    result = {
        'as_of_date': str(as_of_date) if as_of_date else str(timezone.now().date()),
        'reporting_currency': rep_curr,
        'accounts': items,
        'total_debit': total_consolidated_debit,
        'total_credit': total_consolidated_credit,
        'imbalance': imbalance,
        'is_balanced': abs(imbalance) < Decimal('0.0100')
    }
    CacheManager.set(cache_key, result, timeout=1800)
    return result
