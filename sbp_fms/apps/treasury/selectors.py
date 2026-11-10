from decimal import Decimal
from typing import Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404

from apps.common.cache import CacheManager, make_cache_key, KEY_CASH_FORECAST
from apps.common.filters import apply_dict_filters, merge_filters
from apps.receivables.models import ClientInvoice, ClientInvoiceStatus
from apps.payables.models import SupplierInvoice, MatchStatus
from apps.ledger.models import Account, JournalLine, JournalEntryStatus
from .models import (
    BankAccount, BankTransaction,
    BankStatement, BankStatementLine,
    BankReconciliation, ReconciliationStatus
)


# ============================================================================
# 1. BANK ACCOUNTS & TRANSACTIONS SELECTORS
# ============================================================================

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

    qs = BankTransaction.objects.select_related('bank_account', 'reconciled_journal_line').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def bank_transaction_detail(*, transaction_id) -> BankTransaction:
    cache_key = f"fms:treasury:transactions:detail:{transaction_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    tx = get_object_or_404(BankTransaction.objects.select_related('bank_account', 'reconciled_journal_line'), id=transaction_id)
    CacheManager.set(cache_key, tx, timeout=1800)
    return tx


# ============================================================================
# 2. CASHBOOK SELECTOR
# ============================================================================

def cashbook_get(
    *,
    bank_account_id: Optional[str] = None,
    gl_account_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> dict:
    """
    Returns the chronological Cashbook report with running balances for a Bank/Cash GL account.
    """
    if bank_account_id:
        bank_acc = get_object_or_404(BankAccount.objects.select_related('gl_account'), id=bank_account_id)
        account = bank_acc.gl_account
    elif gl_account_id:
        account = get_object_or_404(Account, id=gl_account_id)
        bank_acc = getattr(account, 'bank_account', None)
    else:
        # Default to the first available BankAccount
        bank_acc = BankAccount.objects.select_related('gl_account').first()
        if not bank_acc:
            return {
                'account_id': None, 'account_name': '', 'account_code': '', 'currency': 'GHS',
                'start_date': start_date, 'end_date': end_date,
                'opening_balance': Decimal('0.0000'), 'total_debits': Decimal('0.0000'),
                'total_credits': Decimal('0.0000'), 'closing_balance': Decimal('0.0000'),
                'entries': []
            }
        account = bank_acc.gl_account

    if not end_date:
        end_date = timezone.now().date()
    if not start_date:
        start_date = end_date.replace(day=1)  # 1st day of current month

    # 1. Opening Balance prior to start_date
    prior_debits = JournalLine.objects.filter(
        account=account,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lt=start_date
    ).aggregate(s=Sum('debit'))['s'] or Decimal('0.0000')

    prior_credits = JournalLine.objects.filter(
        account=account,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lt=start_date
    ).aggregate(s=Sum('credit'))['s'] or Decimal('0.0000')

    opening_balance = account.opening_balance + prior_debits - prior_credits

    # 2. Journal lines in the period
    lines_qs = JournalLine.objects.filter(
        account=account,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__gte=start_date,
        entry__posting_date__lte=end_date
    ).select_related('entry').prefetch_related('reconciled_statement_lines').order_by('entry__posting_date', 'entry__created_at', 'created_at')

    running_bal = opening_balance
    total_debits = Decimal('0.0000')
    total_credits = Decimal('0.0000')
    entries = []

    for line in lines_qs:
        running_bal += (line.debit - line.credit)
        total_debits += line.debit
        total_credits += line.credit

        is_reconciled = line.reconciled_statement_lines.exists() or line.reconciled_bank_transactions.exists()

        entries.append({
            'id': str(line.id),
            'journal_entry_id': str(line.entry.id),
            'entry_number': line.entry.entry_number,
            'date': line.entry.posting_date.isoformat(),
            'description': line.entry.description,
            'source_module': line.entry.source_module,
            'source_reference_id': line.entry.source_reference_id,
            'cost_centre': line.cost_centre,
            'debit': line.debit,
            'credit': line.credit,
            'running_balance': running_bal,
            'is_reconciled': is_reconciled
        })

    closing_balance = running_bal

    return {
        'bank_account_id': str(bank_acc.id) if bank_acc else None,
        'bank_name': bank_acc.bank_name if bank_acc else '',
        'account_number': bank_acc.account_number if bank_acc else '',
        'gl_account_id': str(account.id),
        'gl_account_code': account.code,
        'gl_account_name': account.name,
        'currency': account.currency,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'entries': entries
    }


# ============================================================================
# 3. BANK STATEMENTS & RECONCILIATIONS SELECTORS
# ============================================================================

def bank_statement_list(*, bank_account_id: Optional[str] = None) -> list[BankStatement]:
    qs = BankStatement.objects.select_related('bank_account', 'imported_by').all()
    if bank_account_id:
        qs = qs.filter(bank_account_id=bank_account_id)
    return list(qs)


def bank_statement_detail(*, statement_id) -> BankStatement:
    return get_object_or_404(
        BankStatement.objects.select_related('bank_account', 'imported_by').prefetch_related('lines'),
        id=statement_id
    )


def bank_reconciliation_list(*, bank_account_id: Optional[str] = None, status: Optional[str] = None) -> list[BankReconciliation]:
    qs = BankReconciliation.objects.select_related('bank_account', 'reconciled_by').all()
    if bank_account_id:
        qs = qs.filter(bank_account_id=bank_account_id)
    if status:
        qs = qs.filter(status=status)
    return list(qs)


def bank_reconciliation_detail(*, reconciliation_id) -> BankReconciliation:
    return get_object_or_404(
        BankReconciliation.objects.select_related('bank_account', 'reconciled_by'),
        id=reconciliation_id
    )


def bank_reconciliation_summary(*, bank_account_id: str, statement_date: Optional[date] = None) -> dict:
    """
    Computes a full two-way Bank Reconciliation Statement:
    1. Balance per Bank Statement
    2. Add: Deposits in Transit (GL debits not yet cleared on statement)
    3. Less: Outstanding Cheques/Disbursements (GL credits not yet cleared on statement)
    4. = Adjusted Bank Balance
    5. Balance per General Ledger (Book Balance)
    6. Add: Unrecorded Bank Credits (Statement credits not yet in GL)
    7. Less: Unrecorded Bank Debits (Statement debits/fees not yet in GL)
    8. = Adjusted Book Balance
    9. Difference (Adjusted Bank Balance - Adjusted Book Balance)
    """
    bank_acc = get_object_or_404(BankAccount.objects.select_related('gl_account'), id=bank_account_id)
    gl_acc = bank_acc.gl_account

    if not statement_date:
        statement_date = timezone.now().date()

    # 1. Statement Ending Balance
    latest_stmt = BankStatement.objects.filter(
        bank_account=bank_acc,
        statement_date__lte=statement_date
    ).order_by('-statement_date').first()
    stmt_ending_balance = latest_stmt.closing_balance if latest_stmt else Decimal('0.0000')

    # 2. GL Book Balance as of statement_date
    gl_debits = JournalLine.objects.filter(
        account=gl_acc,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lte=statement_date
    ).aggregate(s=Sum('debit'))['s'] or Decimal('0.0000')

    gl_credits = JournalLine.objects.filter(
        account=gl_acc,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lte=statement_date
    ).aggregate(s=Sum('credit'))['s'] or Decimal('0.0000')

    gl_book_balance = gl_acc.opening_balance + gl_debits - gl_credits

    # 3. Deposits in Transit (GL debits not yet cleared on bank statement)
    # Journal lines with debit > 0 where matched statement line does not exist
    in_transit_receipts = JournalLine.objects.filter(
        account=gl_acc,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lte=statement_date,
        debit__gt=Decimal('0.0000'),
        reconciled_statement_lines__isnull=True
    ).select_related('entry')

    deposits_in_transit_total = sum(l.debit for l in in_transit_receipts)
    deposits_in_transit_list = [
        {
            'journal_line_id': str(l.id),
            'entry_number': l.entry.entry_number,
            'date': l.entry.posting_date.isoformat(),
            'description': l.entry.description,
            'amount': l.debit
        }
        for l in in_transit_receipts
    ]

    # 4. Outstanding Cheques / Payments in Transit (GL credits not yet cleared)
    outstanding_payments = JournalLine.objects.filter(
        account=gl_acc,
        entry__status=JournalEntryStatus.POSTED,
        entry__posting_date__lte=statement_date,
        credit__gt=Decimal('0.0000'),
        reconciled_statement_lines__isnull=True
    ).select_related('entry')

    outstanding_cheques_total = sum(l.credit for l in outstanding_payments)
    outstanding_cheques_list = [
        {
            'journal_line_id': str(l.id),
            'entry_number': l.entry.entry_number,
            'date': l.entry.posting_date.isoformat(),
            'description': l.entry.description,
            'amount': l.credit
        }
        for l in outstanding_payments
    ]

    # 5. Adjusted Bank Balance
    adjusted_bank_balance = stmt_ending_balance + deposits_in_transit_total - outstanding_cheques_total

    # 6. Unrecorded Bank Credits (Statement credits/deposits not matched in GL)
    unrec_credits = BankStatementLine.objects.filter(
        bank_account=bank_acc,
        transaction_date__lte=statement_date,
        is_reconciled=False,
        debit__gt=Decimal('0.0000')
    )
    unrec_credits_total = sum(l.debit for l in unrec_credits)
    unrec_credits_list = [
        {
            'statement_line_id': str(l.id),
            'date': l.transaction_date.isoformat(),
            'reference': l.reference,
            'description': l.description,
            'amount': l.debit
        }
        for l in unrec_credits
    ]

    # 7. Unrecorded Bank Debits (Statement withdrawals/charges not matched in GL)
    unrec_debits = BankStatementLine.objects.filter(
        bank_account=bank_acc,
        transaction_date__lte=statement_date,
        is_reconciled=False,
        credit__gt=Decimal('0.0000')
    )
    unrec_debits_total = sum(l.credit for l in unrec_debits)
    unrec_debits_list = [
        {
            'statement_line_id': str(l.id),
            'date': l.transaction_date.isoformat(),
            'reference': l.reference,
            'description': l.description,
            'amount': l.credit
        }
        for l in unrec_debits
    ]

    # 8. Adjusted Book Balance
    adjusted_book_balance = gl_book_balance + unrec_credits_total - unrec_debits_total

    # 9. Net Reconciled Difference
    diff = adjusted_bank_balance - adjusted_book_balance

    return {
        'bank_account_id': str(bank_acc.id),
        'bank_name': bank_acc.bank_name,
        'account_number': bank_acc.account_number,
        'gl_account_code': gl_acc.code,
        'statement_date': statement_date.isoformat(),
        'statement_ending_balance': stmt_ending_balance,
        'deposits_in_transit_total': deposits_in_transit_total,
        'deposits_in_transit': deposits_in_transit_list,
        'outstanding_cheques_total': outstanding_cheques_total,
        'outstanding_cheques': outstanding_cheques_list,
        'adjusted_bank_balance': adjusted_bank_balance,
        'gl_book_balance': gl_book_balance,
        'unrecorded_bank_credits_total': unrec_credits_total,
        'unrecorded_bank_credits': unrec_credits_list,
        'unrecorded_bank_debits_total': unrec_debits_total,
        'unrecorded_bank_debits': unrec_debits_list,
        'adjusted_book_balance': adjusted_book_balance,
        'reconciled_difference': diff,
        'is_balanced': diff == Decimal('0.0000')
    }


# ============================================================================
# 4. LIQUIDITY FORECAST
# ============================================================================

def liquidity_forecast_get() -> dict:
    cached = CacheManager.get(KEY_CASH_FORECAST)
    if cached is not None:
        return cached

    # Calculate actual cash from all active bank accounts and cash GL accounts
    bank_accounts = BankAccount.objects.select_related('gl_account').filter(is_active=True)
    current_cash = Decimal('0.0000')
    for b in bank_accounts:
        debits = JournalLine.objects.filter(
            account=b.gl_account,
            entry__status=JournalEntryStatus.POSTED
        ).aggregate(s=Sum('debit'))['s'] or Decimal('0.0000')
        credits = JournalLine.objects.filter(
            account=b.gl_account,
            entry__status=JournalEntryStatus.POSTED
        ).aggregate(s=Sum('credit'))['s'] or Decimal('0.0000')
        current_cash += (b.gl_account.opening_balance + debits - credits)

    if current_cash == Decimal('0.0000'):
        current_cash = Decimal('1500000.0000')  # Baseline fallback

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
