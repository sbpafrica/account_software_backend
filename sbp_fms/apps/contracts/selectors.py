from decimal import Decimal
from django.db.models import Sum, Q
from apps.common.cache import CacheManager, make_cache_key
from apps.receivables.models import ClientInvoice, ClientInvoiceStatus
from apps.payables.models import PaymentVoucher, PaymentVoucherStatus
from apps.ledger.models import JournalLine, AccountType
from .models import Contract


def contract_list(*, client_id: str = None, status: str = None):
    cache_key = make_cache_key("fms:contracts:list", client_id=client_id, status=status)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Contract.objects.select_related('client').all()
    if client_id:
        qs = qs.filter(client_id=client_id)
    if status:
        qs = qs.filter(status=status)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def contract_detail(*, contract_id: str) -> Contract:
    cache_key = make_cache_key("fms:contracts:detail", identifier=contract_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    contract = Contract.objects.select_related('client').get(id=contract_id)
    CacheManager.set(cache_key, contract, timeout=1800)
    return contract


def contract_profitability_get(*, contract_id: str) -> dict:
    cache_key = make_cache_key("fms:contracts:profitability", identifier=contract_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    contract = contract_detail(contract_id=contract_id)

    # 1. Billed Revenue from Client Invoices
    inv_qs = ClientInvoice.objects.filter(
        client=contract.client,
        status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID, ClientInvoiceStatus.PAID]
    )
    specific_invs = inv_qs.filter(
        Q(lines__description__icontains=contract.contract_number) |
        Q(invoice_number__icontains=contract.contract_number)
    ).distinct()
    if specific_invs.exists():
        inv_qs = specific_invs

    # Invoiced subtotal (net of sales tax) represents earned revenue
    billed_revenue = sum(inv.subtotal for inv in inv_qs)
    total_tax_collected = sum(inv.tax_amount for inv in inv_qs)
    total_amount_billed = sum(inv.total_amount for inv in inv_qs)
    cash_collected = sum(inv.amount_paid for inv in inv_qs)
    ar_outstanding = total_amount_billed - cash_collected

    # 2. Direct Workforce and Direct Expenses
    pv_qs = PaymentVoucher.objects.filter(status=PaymentVoucherStatus.PAID)
    if contract.cost_centre:
        pv_qs = pv_qs.filter(Q(client_id=contract.client.id) | Q(cost_centre=contract.cost_centre))
    else:
        pv_qs = pv_qs.filter(client_id=contract.client.id)

    direct_expenses = sum(v.net_amount for v in pv_qs)

    # 3. Direct Cost GL lines
    gl_lines = JournalLine.objects.filter(
        entry__status='POSTED',
        account__account_type=AccountType.DIRECT_COST
    )
    if contract.cost_centre:
        gl_lines = gl_lines.filter(cost_centre=contract.cost_centre)
        direct_labour = sum(l.debit - l.credit for l in gl_lines)
    else:
        direct_labour = Decimal('0.0000')

    total_direct_costs = direct_expenses + direct_labour
    gross_profit = billed_revenue - total_direct_costs

    gross_margin_pct = (
        (gross_profit / billed_revenue * 100).quantize(Decimal('0.01'))
        if billed_revenue > 0 else Decimal('0.00')
    )

    contract_burn_pct = (
        (billed_revenue / contract.total_contract_value * 100).quantize(Decimal('0.01'))
        if contract.total_contract_value > 0 else Decimal('0.00')
    )

    result = {
        'contract_id': str(contract.id),
        'contract_number': contract.contract_number,
        'contract_title': contract.title,
        'client_id': str(contract.client.id),
        'client_name': contract.client.name,
        'status': contract.status,
        'total_contract_value': contract.total_contract_value,
        'cost_centre': contract.cost_centre,
        'billed_revenue': billed_revenue,
        'cash_collected': cash_collected,
        'ar_outstanding': ar_outstanding,
        'direct_expenses': direct_expenses,
        'direct_labour': direct_labour,
        'total_direct_costs': total_direct_costs,
        'gross_profit': gross_profit,
        'gross_margin_pct': gross_margin_pct,
        'contract_realization_pct': contract_burn_pct,
        'is_profitable': gross_profit >= Decimal('0.0000')
    }
    CacheManager.set(cache_key, result, timeout=1800)
    return result
