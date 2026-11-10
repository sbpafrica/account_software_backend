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


def profit_and_loss_get(
    *,
    start_date=None,
    end_date=None,
    department=None,
    cost_centre=None,
    country_code=None
) -> dict:
    """
    Computes standard Profit and Loss Statement:
    Turnover / Revenue
    Less: Cost of Sales / Direct Cost
    = Gross Profit (and GP Margin %)
    Less: Operating Expenses (OPEX)
    = Operating Profit / Net Profit (and Operating Margin %)
    """
    if not end_date:
        end_date = timezone.now().date()
    if not start_date:
        start_date = end_date.replace(month=1, day=1)

    qs = JournalLine.objects.filter(
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__gte=start_date,
        entry__posting_date__lte=end_date
    )
    if country_code and country_code != 'ALL':
        qs = qs.filter(country_code=country_code)
    if cost_centre:
        qs = qs.filter(cost_centre=cost_centre)

    # 1. Revenue accounts (Credit - Debit)
    rev_accounts = Account.objects.filter(account_type='REVENUE', is_active=True)
    rev_lines = []
    total_revenue = Decimal('0.0000')
    for acc in rev_accounts:
        agg = qs.filter(account=acc).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        d = agg['d'] or Decimal('0.0000')
        c = agg['c'] or Decimal('0.0000')
        net_rev = c - d
        if net_rev != 0:
            rev_lines.append({
                'account_id': str(acc.id),
                'code': acc.code,
                'name': acc.name,
                'amount': net_rev
            })
            total_revenue += net_rev

    # 2. Direct Costs / Cost of Sales (Debit - Credit)
    cos_accounts = Account.objects.filter(account_type='DIRECT_COST', is_active=True)
    cos_lines = []
    total_cost_of_sales = Decimal('0.0000')
    for acc in cos_accounts:
        agg = qs.filter(account=acc).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        d = agg['d'] or Decimal('0.0000')
        c = agg['c'] or Decimal('0.0000')
        net_cos = d - c
        if net_cos != 0:
            cos_lines.append({
                'account_id': str(acc.id),
                'code': acc.code,
                'name': acc.name,
                'amount': net_cos
            })
            total_cost_of_sales += net_cos

    gross_profit = total_revenue - total_cost_of_sales
    gp_margin_pct = (gross_profit / total_revenue * Decimal('100.0')) if total_revenue > 0 else Decimal('0.0000')

    # 3. Operating Expenses (Debit - Credit)
    opex_accounts = Account.objects.filter(account_type='OPEX', is_active=True)
    opex_lines = []
    total_operating_expenses = Decimal('0.0000')
    for acc in opex_accounts:
        agg = qs.filter(account=acc).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        d = agg['d'] or Decimal('0.0000')
        c = agg['c'] or Decimal('0.0000')
        net_opex = d - c
        if net_opex != 0:
            opex_lines.append({
                'account_id': str(acc.id),
                'code': acc.code,
                'name': acc.name,
                'amount': net_opex
            })
            total_operating_expenses += net_opex

    net_profit = gross_profit - total_operating_expenses
    net_margin_pct = (net_profit / total_revenue * Decimal('100.0')) if total_revenue > 0 else Decimal('0.0000')

    return {
        'start_date': str(start_date),
        'end_date': str(end_date),
        'country_code': country_code or 'ALL',
        'revenue_items': rev_lines,
        'total_revenue': total_revenue,
        'cost_of_sales_items': cos_lines,
        'total_cost_of_sales': total_cost_of_sales,
        'gross_profit': gross_profit,
        'gross_profit_margin_pct': gp_margin_pct.quantize(Decimal('0.01')),
        'operating_expense_items': opex_lines,
        'total_operating_expenses': total_operating_expenses,
        'operating_profit': net_profit,
        'net_profit': net_profit,
        'net_margin_pct': net_margin_pct.quantize(Decimal('0.01'))
    }


def balance_sheet_get(*, as_of_date=None, country_code=None) -> dict:
    """
    Computes Balance Sheet Statement:
    Total Assets (Current Assets + Non-Current Assets)
    Total Liabilities (Current Liabilities + Non-Current Liabilities)
    Total Equity (Equity Accounts + Current Period Net Profit)
    Check: Total Assets == Total Liabilities + Total Equity
    """
    if not as_of_date:
        as_of_date = timezone.now().date()

    qs = JournalLine.objects.filter(
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lte=as_of_date
    )
    if country_code and country_code != 'ALL':
        qs = qs.filter(country_code=country_code)

    # 1. Assets
    current_assets = []
    non_current_assets = []
    total_current_assets = Decimal('0.0000')
    total_non_current_assets = Decimal('0.0000')

    asset_accounts = Account.objects.filter(account_type='ASSET', is_active=True).order_by('code')
    for acc in asset_accounts:
        agg = qs.filter(account=acc).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        d = agg['d'] or Decimal('0.0000')
        c = agg['c'] or Decimal('0.0000')
        bal = acc.opening_balance + d - c
        if bal != 0 or acc.opening_balance != 0:
            item = {'account_id': str(acc.id), 'code': acc.code, 'name': acc.name, 'balance': bal}
            # Account code < 1500 or subtype current asset
            if acc.code < '1500' or acc.subtype in ['CASH', 'BANK', 'RECEIVABLE']:
                current_assets.append(item)
                total_current_assets += bal
            else:
                non_current_assets.append(item)
                total_non_current_assets += bal

    total_assets = total_current_assets + total_non_current_assets

    # 2. Liabilities
    current_liabilities = []
    non_current_liabilities = []
    total_current_liabilities = Decimal('0.0000')
    total_non_current_liabilities = Decimal('0.0000')

    liab_accounts = Account.objects.filter(account_type='LIABILITY', is_active=True).order_by('code')
    for acc in liab_accounts:
        agg = qs.filter(account=acc).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        d = agg['d'] or Decimal('0.0000')
        c = agg['c'] or Decimal('0.0000')
        bal = acc.opening_balance + c - d  # Normal credit balance
        if bal != 0 or acc.opening_balance != 0:
            item = {'account_id': str(acc.id), 'code': acc.code, 'name': acc.name, 'balance': bal}
            if acc.code < '2500':
                current_liabilities.append(item)
                total_current_liabilities += bal
            else:
                non_current_liabilities.append(item)
                total_non_current_liabilities += bal

    total_liabilities = total_current_liabilities + total_non_current_liabilities

    # 3. Equity
    equity_items = []
    total_equity_accounts = Decimal('0.0000')
    equity_accounts = Account.objects.filter(account_type='EQUITY', is_active=True).order_by('code')
    for acc in equity_accounts:
        agg = qs.filter(account=acc).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        d = agg['d'] or Decimal('0.0000')
        c = agg['c'] or Decimal('0.0000')
        bal = acc.opening_balance + c - d
        if bal != 0 or acc.opening_balance != 0:
            equity_items.append({'account_id': str(acc.id), 'code': acc.code, 'name': acc.name, 'balance': bal})
            total_equity_accounts += bal

    # Net income from revenue - (direct cost + opex) up to as_of_date
    rev_agg = qs.filter(account__account_type='REVENUE').aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    tot_rev = (rev_agg['c'] or Decimal('0.0000')) - (rev_agg['d'] or Decimal('0.0000'))

    exp_agg = qs.filter(account__account_type__in=['DIRECT_COST', 'OPEX']).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    tot_exp = (exp_agg['d'] or Decimal('0.0000')) - (exp_agg['c'] or Decimal('0.0000'))

    current_period_earnings = tot_rev - tot_exp
    total_equity = total_equity_accounts + current_period_earnings

    total_liab_and_equity = total_liabilities + total_equity
    difference = total_assets - total_liab_and_equity

    return {
        'as_of_date': str(as_of_date),
        'country_code': country_code or 'ALL',
        'current_assets': current_assets,
        'total_current_assets': total_current_assets,
        'non_current_assets': non_current_assets,
        'total_non_current_assets': total_non_current_assets,
        'total_assets': total_assets,
        'current_liabilities': current_liabilities,
        'total_current_liabilities': total_current_liabilities,
        'non_current_liabilities': non_current_liabilities,
        'total_non_current_liabilities': total_non_current_liabilities,
        'total_liabilities': total_liabilities,
        'equity_items': equity_items,
        'total_equity_accounts': total_equity_accounts,
        'current_period_earnings': current_period_earnings,
        'total_equity': total_equity,
        'total_liabilities_and_equity': total_liab_and_equity,
        'difference': difference,
        'is_balanced': difference == Decimal('0.0000')
    }


def cash_flow_statement_get(*, start_date=None, end_date=None, country_code=None) -> dict:
    """
    Computes Cash Flow Statement (Indirect Method):
    Operating Activities + Investing Activities + Financing Activities
    = Net change in cash + beginning cash = ending cash
    """
    if not end_date:
        end_date = timezone.now().date()
    if not start_date:
        start_date = end_date.replace(month=1, day=1)

    pnl = profit_and_loss_get(start_date=start_date, end_date=end_date, country_code=country_code)
    net_income = pnl['net_profit']

    # Working capital changes
    qs_prior = JournalLine.objects.filter(entry__status=JournalEntryStatus.POSTED, entry__posting_date__lt=start_date)
    qs_cur = JournalLine.objects.filter(entry__status=JournalEntryStatus.POSTED, entry__posting_date__lte=end_date)
    if country_code and country_code != 'ALL':
        qs_prior = qs_prior.filter(country_code=country_code)
        qs_cur = qs_cur.filter(country_code=country_code)

    # Change in AR (code 1100 accounts)
    ar_prior = qs_prior.filter(account__code__startswith='1100').aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ar_cur = qs_cur.filter(account__code__startswith='1100').aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ar_bal_prior = (ar_prior['d'] or Decimal('0.0000')) - (ar_prior['c'] or Decimal('0.0000'))
    ar_bal_cur = (ar_cur['d'] or Decimal('0.0000')) - (ar_cur['c'] or Decimal('0.0000'))
    ar_change = -(ar_bal_cur - ar_bal_prior)  # Increase in AR is cash outflow

    # Change in AP (code 2000 accounts)
    ap_prior = qs_prior.filter(account__code__startswith='2000').aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ap_cur = qs_cur.filter(account__code__startswith='2000').aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ap_bal_prior = (ap_prior['c'] or Decimal('0.0000')) - (ap_prior['d'] or Decimal('0.0000'))
    ap_bal_cur = (ap_cur['c'] or Decimal('0.0000')) - (ap_cur['d'] or Decimal('0.0000'))
    ap_change = (ap_bal_cur - ap_bal_prior)  # Increase in AP is cash inflow

    operating_cash_flow = net_income + ar_change + ap_change

    # Investing activities (Fixed assets - code 1500 accounts)
    fa_lines = JournalLine.objects.filter(
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__gte=start_date,
        entry__posting_date__lte=end_date,
        account__code__startswith='1500'
    ).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    investing_cash_flow = -((fa_lines['d'] or Decimal('0.0000')) - (fa_lines['c'] or Decimal('0.0000')))

    # Financing activities (Equity & Long term debt)
    fin_lines = JournalLine.objects.filter(
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__gte=start_date,
        entry__posting_date__lte=end_date,
        account__account_type__in=['EQUITY', 'LIABILITY'],
        account__code__gte='2500'
    ).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    financing_cash_flow = (fin_lines['c'] or Decimal('0.0000')) - (fin_lines['d'] or Decimal('0.0000'))

    net_cash_change = operating_cash_flow + investing_cash_flow + financing_cash_flow

    # Cash at beginning and end
    cash_accounts = Account.objects.filter(account_type='ASSET', code__startswith='10', is_active=True)
    if country_code and country_code != 'ALL':
        cash_accounts = cash_accounts.filter(country_code=country_code)
    initial_opening_cash = sum(acc.opening_balance for acc in cash_accounts)

    cash_prior = qs_prior.filter(account__code__startswith='10').aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    beginning_cash = initial_opening_cash + (cash_prior['d'] or Decimal('0.0000')) - (cash_prior['c'] or Decimal('0.0000'))
    ending_cash = beginning_cash + net_cash_change

    return {
        'start_date': str(start_date),
        'end_date': str(end_date),
        'country_code': country_code or 'ALL',
        'net_income': net_income,
        'change_in_receivables': ar_change,
        'change_in_payables': ap_change,
        'operating_cash_flow': operating_cash_flow,
        'investing_cash_flow': investing_cash_flow,
        'financing_cash_flow': financing_cash_flow,
        'net_cash_change': net_cash_change,
        'beginning_cash': beginning_cash,
        'ending_cash': ending_cash
    }


def gl_account_statement_get(*, account_id, start_date=None, end_date=None) -> dict:
    """
    Returns running ledger activity for a specific GL account.
    """
    account = get_object_or_404(Account, id=account_id)
    if not end_date:
        end_date = timezone.now().date()
    if not start_date:
        start_date = end_date.replace(month=1, day=1)

    # Opening balance prior to start_date
    prior_agg = JournalLine.objects.filter(
        account=account,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lt=start_date
    ).aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    p_d = prior_agg['d'] or Decimal('0.0000')
    p_c = prior_agg['c'] or Decimal('0.0000')

    # Debit normal for Assets, Direct Cost, OPEX; Credit normal for Liabilities, Equity, Revenue
    is_debit_normal = account.account_type in ['ASSET', 'DIRECT_COST', 'OPEX']
    if is_debit_normal:
        opening_balance = account.opening_balance + p_d - p_c
    else:
        opening_balance = account.opening_balance + p_c - p_d

    lines_qs = JournalLine.objects.filter(
        account=account,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__gte=start_date,
        entry__posting_date__lte=end_date
    ).select_related('entry').order_by('entry__posting_date', 'entry__created_at')

    running_bal = opening_balance
    total_debits = Decimal('0.0000')
    total_credits = Decimal('0.0000')
    entries = []

    for line in lines_qs:
        total_debits += line.debit
        total_credits += line.credit
        if is_debit_normal:
            running_bal += (line.debit - line.credit)
        else:
            running_bal += (line.credit - line.debit)

        entries.append({
            'journal_entry_id': str(line.entry.id),
            'entry_number': line.entry.entry_number,
            'posting_date': str(line.entry.posting_date),
            'description': line.entry.description,
            'source_module': line.entry.source_module,
            'source_reference_id': line.entry.source_reference_id,
            'cost_centre': line.cost_centre,
            'debit': line.debit,
            'credit': line.credit,
            'running_balance': running_bal
        })

    return {
        'account_id': str(account.id),
        'code': account.code,
        'name': account.name,
        'account_type': account.account_type,
        'currency': account.currency,
        'start_date': str(start_date),
        'end_date': str(end_date),
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': running_bal,
        'entries': entries
    }


def ceo_executive_dashboard_get(*, as_of_date=None, country_code: str = None) -> dict:
    """
    Enterprise Executive C-Level Intelligence Dashboard selector.
    Synthesizes real-time metrics across Treasury, Receivables, Payables, and GL.
    """
    from django.utils import timezone
    from apps.treasury.models import BankAccount
    from apps.receivables.models import ClientInvoice, ClientInvoiceStatus
    from apps.payables.models import SupplierInvoice, MatchStatus
    from .models import AccountType

    from datetime import datetime, date
    if not as_of_date:
        as_of_date = timezone.now().date()
    elif isinstance(as_of_date, str):
        as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()

    # 1. Treasury / Liquidity
    bank_qs = BankAccount.objects.filter(is_active=True).select_related('gl_account')
    banks_summary = []
    total_cash_liquidity = Decimal('0.0000')

    for b in bank_qs:
        # Calculate current running balance from GL
        lines = JournalLine.objects.filter(
            account=b.gl_account,
            entry__status=JournalEntryStatus.POSTED,
            entry__posting_date__lte=as_of_date
        )
        totals = lines.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        bal = (totals['d'] or Decimal('0')) - (totals['c'] or Decimal('0'))
        total_cash_liquidity += bal
        banks_summary.append({
            'bank_account_id': str(b.id),
            'bank_name': b.bank_name,
            'account_number': b.account_number,
            'currency': b.gl_account.currency if b.gl_account else 'GHS',
            'balance': bal
        })

    # 2. Receivables (AR)
    inv_qs = ClientInvoice.objects.filter(
        issue_date__lte=as_of_date,
        status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID, ClientInvoiceStatus.PAID]
    )
    if country_code:
        inv_qs = inv_qs.filter(client__country_code=country_code)

    total_invoiced_ytd = sum(inv.total_amount for inv in inv_qs if inv.issue_date.year == as_of_date.year)
    total_collections_ytd = sum(inv.amount_paid for inv in inv_qs if inv.issue_date.year == as_of_date.year)
    
    open_invoices = [inv for inv in inv_qs if inv.status != ClientInvoiceStatus.PAID]
    total_ar_outstanding = sum((inv.total_amount - inv.amount_paid) for inv in open_invoices)
    overdue_ar = sum(
        (inv.total_amount - inv.amount_paid) for inv in open_invoices
        if inv.due_date and inv.due_date < as_of_date
    )

    # 3. Payables (AP)
    bill_qs = SupplierInvoice.objects.filter(
        created_at__date__lte=as_of_date
    )
    if country_code:
        bill_qs = bill_qs.filter(supplier__country_code=country_code)

    open_bills = [b for b in bill_qs if b.match_status != MatchStatus.PAID]
    total_ap_outstanding = sum((b.net_payable_amount - b.amount_paid) for b in open_bills)
    overdue_ap = sum(
        (b.net_payable_amount - b.amount_paid) for b in open_bills
        if b.due_date and b.due_date < as_of_date
    )

    # 4. Profit & Loss YTD (from GL)
    ytd_lines = JournalLine.objects.filter(
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__year=as_of_date.year,
        entry__posting_date__lte=as_of_date
    )
    if country_code:
        ytd_lines = ytd_lines.filter(country_code=country_code)

    # Revenue (CR - DR)
    rev_lines = ytd_lines.filter(account__account_type=AccountType.REVENUE)
    rev_tot = rev_lines.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ytd_revenue = (rev_tot['c'] or Decimal('0')) - (rev_tot['d'] or Decimal('0'))

    # Direct Costs (DR - CR)
    cos_lines = ytd_lines.filter(account__account_type=AccountType.DIRECT_COST)
    cos_tot = cos_lines.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ytd_cost_of_sales = (cos_tot['d'] or Decimal('0')) - (cos_tot['c'] or Decimal('0'))

    ytd_gross_profit = ytd_revenue - ytd_cost_of_sales
    ytd_gross_margin_pct = (ytd_gross_profit / ytd_revenue * 100).quantize(Decimal('0.01')) if ytd_revenue > 0 else Decimal('0.00')

    # OPEX (DR - CR)
    opex_lines = ytd_lines.filter(account__account_type=AccountType.OPEX)
    opex_tot = opex_lines.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
    ytd_opex = (opex_tot['d'] or Decimal('0')) - (opex_tot['c'] or Decimal('0'))

    ytd_net_profit = ytd_gross_profit - ytd_opex
    ytd_net_margin_pct = (ytd_net_profit / ytd_revenue * 100).quantize(Decimal('0.01')) if ytd_revenue > 0 else Decimal('0.00')

    # 5. Working Capital & Liquidity Ratios
    current_assets = total_cash_liquidity + total_ar_outstanding
    current_liabilities = total_ap_outstanding
    working_capital = current_assets - current_liabilities
    current_ratio = (current_assets / current_liabilities).quantize(Decimal('0.01')) if current_liabilities > 0 else Decimal('999.99')

    # 6. Burn Rate & Runway
    months_elapsed = max(1, as_of_date.month)
    monthly_burn_rate = (ytd_opex / Decimal(str(months_elapsed))).quantize(Decimal('0.0001'))
    cash_runway_months = (
        (total_cash_liquidity / monthly_burn_rate).quantize(Decimal('0.1'))
        if monthly_burn_rate > 0 else Decimal('99.9')
    )

    return {
        'as_of_date': str(as_of_date),
        'country_code': country_code or 'ALL',
        'liquidity': {
            'total_cash_and_bank': total_cash_liquidity,
            'bank_accounts': banks_summary
        },
        'receivables': {
            'total_ar_outstanding': total_ar_outstanding,
            'overdue_ar': overdue_ar,
            'ytd_invoiced': total_invoiced_ytd,
            'ytd_collected': total_collections_ytd,
            'collection_rate_pct': ((total_collections_ytd / total_invoiced_ytd * 100).quantize(Decimal('0.01')) if total_invoiced_ytd > 0 else Decimal('0.00'))
        },
        'payables': {
            'total_ap_outstanding': total_ap_outstanding,
            'overdue_ap': overdue_ap
        },
        'working_capital': {
            'current_assets': current_assets,
            'current_liabilities': current_liabilities,
            'net_working_capital': working_capital,
            'current_ratio': current_ratio
        },
        'performance_ytd': {
            'revenue': ytd_revenue,
            'cost_of_sales': ytd_cost_of_sales,
            'gross_profit': ytd_gross_profit,
            'gross_margin_pct': ytd_gross_margin_pct,
            'operating_expenses': ytd_opex,
            'net_profit': ytd_net_profit,
            'net_margin_pct': ytd_net_margin_pct
        },
        'runway': {
            'monthly_burn_rate': monthly_burn_rate,
            'cash_runway_months': cash_runway_months
        }
    }


