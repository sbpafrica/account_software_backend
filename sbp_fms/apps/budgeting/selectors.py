from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q
from apps.common.cache import CacheManager, make_cache_key
from apps.ledger.models import Account, JournalLine
from apps.payables.models import PurchaseOrder, PaymentVoucher, PaymentVoucherStatus
from .models import Budget, BudgetLine, BudgetStatus


def budget_list(*, financial_year: int = None, department: str = None, status: str = None):
    cache_key = make_cache_key("fms:budget:list", year=financial_year, dept=department, status=status)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Budget.objects.prefetch_related('lines__account').all()
    if financial_year:
        qs = qs.filter(financial_year=financial_year)
    if department:
        qs = qs.filter(department__iexact=department)
    if status:
        qs = qs.filter(status=status)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def budget_detail(*, budget_id: str) -> Budget:
    cache_key = make_cache_key("fms:budget:detail", identifier=budget_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    budget = Budget.objects.prefetch_related('lines__account').get(id=budget_id)
    CacheManager.set(cache_key, budget, timeout=1800)
    return budget


def budget_variance_report_get(*, budget_id: str):
    """
    Computes real-time budget vs actuals vs commitments variance.
    Actuals: Posted debits to the specified GL expense account for the financial year.
    Commitments: Pending approved Purchase Orders and unposted Payment Vouchers.
    """
    cache_key = make_cache_key("fms:variance:report", identifier=budget_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    budget = budget_detail(budget_id=budget_id)
    year = budget.financial_year

    lines_report = []
    total_planned = Decimal('0.0000')
    total_actual = Decimal('0.0000')
    total_commitments = Decimal('0.0000')

    for bl in budget.lines.all():
        acct = bl.account
        planned = bl.planned_amount
        total_planned += planned

        # 1. Actuals from General Ledger (debit - credit) for the budget year
        gl_qs = JournalLine.objects.filter(
            account=acct,
            entry__status='POSTED',
            entry__posting_date__year=year
        )
        if budget.cost_centre:
            gl_qs = gl_qs.filter(cost_centre=budget.cost_centre)

        gl_totals = gl_qs.aggregate(d=Sum('debit'), c=Sum('credit'))
        debit = gl_totals['d'] or Decimal('0.0000')
        credit = gl_totals['c'] or Decimal('0.0000')
        actual_spent = (debit - credit).quantize(Decimal('0.0001'))
        total_actual += actual_spent

        # 2. Pending Commitments (Unsettled payment vouchers or open PO lines for this account/cost centre)
        pv_qs = PaymentVoucher.objects.filter(
            status__in=[PaymentVoucherStatus.SUBMITTED, PaymentVoucherStatus.REVIEWED, PaymentVoucherStatus.APPROVED],
            voucher_date__year=year
        )
        if budget.cost_centre:
            pv_qs = pv_qs.filter(cost_centre=budget.cost_centre)
        pv_comm = sum(
            l.amount for pv in pv_qs for l in pv.lines.filter(account=acct)
        )
        total_commitments += pv_comm

        # 3. Available balance & variance
        committed_plus_spent = actual_spent + pv_comm
        available = planned - committed_plus_spent
        variance_pct = ((committed_plus_spent / planned) * 100).quantize(Decimal('0.01')) if planned > 0 else Decimal('0.00')

        lines_report.append({
            'line_id': str(bl.id),
            'account_id': str(acct.id),
            'account_code': acct.code,
            'account_name': acct.name,
            'planned_amount': planned,
            'actual_spent': actual_spent,
            'pending_commitments': pv_comm,
            'total_absorbed': committed_plus_spent,
            'available_balance': available,
            'utilization_rate_pct': variance_pct,
            'is_overbudget': available < Decimal('0.0000')
        })

    net_available = total_planned - (total_actual + total_commitments)
    overall_utilization = ((total_actual + total_commitments) / total_planned * 100).quantize(Decimal('0.01')) if total_planned > 0 else Decimal('0.00')

    result = {
        'budget_id': str(budget.id),
        'budget_name': budget.name,
        'financial_year': budget.financial_year,
        'department': budget.department,
        'cost_centre': budget.cost_centre,
        'status': budget.status,
        'lines': lines_report,
        'total_planned': total_planned,
        'total_actual': total_actual,
        'total_commitments': total_commitments,
        'net_available_balance': net_available,
        'overall_utilization_pct': overall_utilization,
        'is_healthy': net_available >= Decimal('0.0000')
    }
    CacheManager.set(cache_key, result, timeout=1800)
    return result


def budget_pre_commitment_check(*, account_id: str, amount: Decimal,
                                department: str = None, cost_centre: str = None,
                                financial_year: int = None) -> dict:
    """
    Intercepts purchase requisitions / voucher creation to verify budget sufficiency.
    Prevents unauthorized budget overruns.
    """
    amt = Decimal(str(amount))
    if not financial_year:
        financial_year = timezone.now().year

    # Find active/approved budget matching financial year and department/cost_centre
    budget_qs = Budget.objects.filter(
        financial_year=financial_year,
        status=BudgetStatus.APPROVED
    )
    if department:
        budget_qs = budget_qs.filter(department__iexact=department)
    if cost_centre:
        budget_qs = budget_qs.filter(cost_centre=cost_centre)

    budget = budget_qs.first()

    # If no budget exists for this department, we log as no active constraint
    if not budget:
        return {
            'allowed': True,
            'has_budget_constraint': False,
            'planned_amount': None,
            'actual_spent': None,
            'pending_commitments': None,
            'requested_amount': amt,
            'projected_available_balance': None,
            'message': f"No formal approved budget constraint for year {financial_year} / dept '{department}'."
        }

    # Find line for this specific account
    line = budget.lines.filter(account_id=account_id).first()
    if not line:
        return {
            'allowed': False,
            'has_budget_constraint': True,
            'planned_amount': Decimal('0.0000'),
            'actual_spent': Decimal('0.0000'),
            'pending_commitments': Decimal('0.0000'),
            'requested_amount': amt,
            'projected_available_balance': -amt,
            'message': f"Account is not in the approved budget '{budget.name}'."
        }

    # Compute absorbed amount
    planned = line.planned_amount
    gl_totals = JournalLine.objects.filter(
        account_id=account_id,
        entry__status='POSTED',
        entry__posting_date__year=financial_year
    ).aggregate(d=Sum('debit'), c=Sum('credit'))
    actual_spent = (gl_totals['d'] or Decimal('0')) - (gl_totals['c'] or Decimal('0'))

    pv_qs = PaymentVoucher.objects.filter(
        status__in=[PaymentVoucherStatus.SUBMITTED, PaymentVoucherStatus.REVIEWED, PaymentVoucherStatus.APPROVED],
        voucher_date__year=financial_year
    )
    commitments = sum(l.amount for pv in pv_qs for l in pv.lines.filter(account_id=account_id))

    current_available = planned - (actual_spent + commitments)
    projected_available = current_available - amt
    is_allowed = projected_available >= Decimal('0.0000')

    msg = "Budget check passed: sufficient allocation available." if is_allowed else (
        f"Budget breach: Available balance {current_available} is less than requested {amt}."
    )

    return {
        'allowed': is_allowed,
        'has_budget_constraint': True,
        'budget_id': str(budget.id),
        'budget_name': budget.name,
        'planned_amount': planned,
        'actual_spent': actual_spent,
        'pending_commitments': commitments,
        'requested_amount': amt,
        'projected_available_balance': projected_available,
        'message': msg
    }
