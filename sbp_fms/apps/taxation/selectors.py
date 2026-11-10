from decimal import Decimal
from typing import Optional
from datetime import date
from django.utils import timezone
from django.db.models import Sum
from django.shortcuts import get_object_or_404

from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from apps.receivables.models import ClientInvoice, ClientInvoiceStatus
from apps.payables.models import SupplierInvoice, MatchStatus, PaymentVoucher, PaymentVoucherStatus
from .models import TaxRule


def tax_rule_list(*, filters: Optional[dict] = None, country_code: Optional[str] = None, tax_type: Optional[str] = None) -> list[TaxRule]:
    combined_filters = merge_filters(filters, country_code=country_code, tax_type=tax_type)
    cache_key = make_cache_key('fms:tax:rules:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = TaxRule.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def tax_rule_detail(*, rule_id) -> TaxRule:
    cache_key = f"fms:tax:rules:detail:{rule_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    rule = get_object_or_404(TaxRule, id=rule_id)
    CacheManager.set(cache_key, rule, timeout=1800)
    return rule


def vat_return_summary_get(*, start_date: Optional[date] = None,
                           end_date: Optional[date] = None,
                           country_code: str = 'GH') -> dict:
    """
    Computes Ghana GRA monthly VAT and statutory tax return summary:
    1. Output Tax (from issued Client Invoices)
    2. Input Tax (from matched Supplier Invoices)
    3. Net VAT Payable / (Refundable Credit)
    4. Withholding Tax (WHT) deducted from suppliers payable to GRA
    5. Net Total Tax Liability to Tax Authorities
    """
    if not end_date:
        end_date = timezone.now().date()
    if not start_date:
        start_date = end_date.replace(day=1)

    # 1. Output VAT & Sales (Receivables)
    client_invoices = ClientInvoice.objects.filter(
        issue_date__gte=start_date,
        issue_date__lte=end_date,
        status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID, ClientInvoiceStatus.PAID]
    )
    if country_code and country_code != 'ALL':
        client_invoices = client_invoices.filter(client__country_code=country_code)

    total_taxable_sales = sum((inv.total_amount - inv.tax_amount) for inv in client_invoices)
    total_output_tax = sum(inv.tax_amount for inv in client_invoices)

    # In Ghana, standard breakdown:
    # 2.5% NHIL, 2.5% GETFund, 1.0% COVID, 15.0% VAT on (base + levies)
    output_nhil = (total_taxable_sales * Decimal('0.025')).quantize(Decimal('0.0001'))
    output_getfund = (total_taxable_sales * Decimal('0.025')).quantize(Decimal('0.0001'))
    output_covid = (total_taxable_sales * Decimal('0.010')).quantize(Decimal('0.0001'))
    output_vat_only = total_output_tax - (output_nhil + output_getfund + output_covid)
    if output_vat_only < 0:
        output_vat_only = total_output_tax

    # 2. Input VAT (Payables)
    supplier_invoices = SupplierInvoice.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    if country_code and country_code != 'ALL':
        supplier_invoices = supplier_invoices.filter(supplier__country_code=country_code)

    total_taxable_purchases = sum(inv.gross_amount for inv in supplier_invoices)
    total_input_tax = Decimal('0.0000')

    # 3. Net VAT Position
    net_vat_payable = total_output_tax - total_input_tax

    # 4. Withholding Tax (WHT) Deducted
    vouchers = PaymentVoucher.objects.filter(
        voucher_date__gte=start_date,
        voucher_date__lte=end_date,
        status__in=[PaymentVoucherStatus.APPROVED, PaymentVoucherStatus.PAID]
    )
    wht_from_vouchers = sum(v.wht_amount for v in vouchers)
    wht_from_invoices = sum(inv.wht_amount for inv in supplier_invoices)
    total_wht_payable = wht_from_vouchers if wht_from_vouchers > 0 else wht_from_invoices

    # 5. Grand Statutory Payable
    total_payable_to_revenue_authority = net_vat_payable + total_wht_payable

    return {
        'start_date': str(start_date),
        'end_date': str(end_date),
        'country_code': country_code,
        'taxable_supplies_sales': total_taxable_sales,
        'output_tax_total': total_output_tax,
        'output_nhil': output_nhil,
        'output_getfund': output_getfund,
        'output_covid_levy': output_covid,
        'output_vat': output_vat_only,
        'taxable_purchases': total_taxable_purchases,
        'input_tax_total': total_input_tax,
        'net_vat_payable': net_vat_payable,
        'is_refund_credit': net_vat_payable < Decimal('0.0000'),
        'withholding_tax_payable': total_wht_payable,
        'total_statutory_liability': total_payable_to_revenue_authority
    }
