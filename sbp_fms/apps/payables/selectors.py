from typing import Optional
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from .models import Supplier, SupplierInvoice, PurchaseOrder, GoodsReceivedNote
from .models import PaymentVoucher, PaymentVoucherStatus
from decimal import Decimal
from django.utils import timezone


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


def payment_voucher_list(
    *,
    filters: Optional[dict] = None,
    supplier_id: Optional[str] = None,
    status: Optional[str] = None
) -> list[PaymentVoucher]:
    combined_filters = merge_filters(filters, supplier_id=supplier_id, status=status)
    cache_key = make_cache_key('fms:payables:vouchers:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = PaymentVoucher.objects.select_related('supplier', 'bank_account', 'prepared_by', 'approved_by').prefetch_related('lines').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def payment_voucher_detail(*, voucher_id) -> PaymentVoucher:
    cache_key = f"fms:payables:vouchers:detail:{voucher_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    voucher = get_object_or_404(
        PaymentVoucher.objects.select_related('supplier', 'bank_account', 'prepared_by', 'approved_by').prefetch_related('lines'),
        id=voucher_id
    )
    CacheManager.set(cache_key, voucher, timeout=1800)
    return voucher


def ap_aging_report_get(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> dict:
    combined_filters = merge_filters(filters, country_code=country_code)
    target_country = combined_filters.get('country_code') or country_code or 'ALL'
    cache_key = f"fms:ap:aging:{target_country}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    today = timezone.now().date()
    from .models import MatchStatus
    bills = SupplierInvoice.objects.filter(
        match_status__in=[MatchStatus.MATCHED, MatchStatus.PENDING]
    )
    if target_country and target_country != 'ALL':
        bills = bills.filter(supplier__country_code=target_country)

    buckets = {
        'country_code': target_country,
        'current_0_30_days': Decimal('0.0000'),
        'overdue_31_60_days': Decimal('0.0000'),
        'overdue_61_90_days': Decimal('0.0000'),
        'overdue_90_plus_days': Decimal('0.0000'),
        'total_payables': Decimal('0.0000')
    }

    for bill in bills:
        bal = bill.balance_due
        if bal <= 0:
            continue
        due = bill.due_date or bill.created_at.date()
        days_overdue = (today - due).days
        buckets['total_payables'] += bal

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


def supplier_statement_get(*, supplier_id: str, date_from=None, date_to=None) -> dict:
    supplier = get_object_or_404(Supplier, id=supplier_id)
    bills = SupplierInvoice.objects.filter(supplier=supplier)
    vouchers = PaymentVoucher.objects.filter(supplier=supplier, status=PaymentVoucherStatus.PAID)

    if date_from:
        bills = bills.filter(created_at__date__gte=date_from)
        vouchers = vouchers.filter(payment_date__gte=date_from)
    if date_to:
        bills = bills.filter(created_at__date__lte=date_to)
        vouchers = vouchers.filter(payment_date__lte=date_to)

    ledger_entries = []
    running_bal = Decimal('0.0000')

    for b in bills:
        running_bal += b.net_payable_amount
        ledger_entries.append({
            'date': str(b.bill_date or b.created_at.date()),
            'reference': b.invoice_number,
            'type': 'BILL',
            'billed': b.net_payable_amount,
            'paid': Decimal('0.0000'),
            'balance': running_bal
        })

    for v in vouchers:
        running_bal -= v.net_amount
        ledger_entries.append({
            'date': str(v.payment_date or v.created_at.date()),
            'reference': v.voucher_number,
            'type': 'PAYMENT',
            'billed': Decimal('0.0000'),
            'paid': v.net_amount,
            'balance': running_bal
        })

    ledger_entries.sort(key=lambda x: x['date'])

    return {
        'supplier_id': str(supplier.id),
        'supplier_name': supplier.name,
        'tax_id': supplier.tax_id,
        'country_code': supplier.country_code,
        'closing_balance': running_bal,
        'transactions': ledger_entries
    }


def expense_claim_list(
    *,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    claim_type: Optional[str] = None
) -> list:
    from .models import ExpenseClaim
    qs = ExpenseClaim.objects.select_related('employee', 'approved_by', 'settlement_voucher').all()
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if status:
        qs = qs.filter(status=status)
    if claim_type:
        qs = qs.filter(claim_type=claim_type)
    return list(qs)


def expense_claim_detail(*, claim_id: str):
    from .models import ExpenseClaim
    return get_object_or_404(
        ExpenseClaim.objects.select_related('employee', 'approved_by', 'settlement_voucher').prefetch_related('lines__expense_account'),
        id=claim_id
    )


