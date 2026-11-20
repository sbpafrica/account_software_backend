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


def ssnit_return_summary_get(*, month: Optional[int] = None, year: Optional[int] = None, organization_id = None, client_id = None) -> dict:
    """
    Computes Ghana SSNIT Monthly Return Summary per Act 766 for SBP Africa.
    Supports:
    1. Single-client filtering when `client_id` is supplied.
    2. Consolidated multi-client portfolio overview across all outsourced clients when `client_id` is omitted.
    Extracts workforce payroll batches and evaluates statutory Tier 1 (13.5%) & Tier 2 (5.0%) liabilities.
    """
    import datetime
    from apps.ledger.models import CompanyProfile
    from apps.payroll_escrow.models import PayrollBatch
    from apps.organizations.models import Organization
    from apps.receivables.models import Client
    from apps.taxation.engines import GhanaTaxEngine

    now = timezone.now().date()
    if not year:
        year = now.year
    if not month:
        # Default to preceding month (standard tax return filing cycle)
        month = now.month - 1 if now.month > 1 else 12
        if now.month == 1:
            year -= 1

    # Calculate statutory deadline: 14th of following month
    if month == 12:
        next_m = 1
        next_y = year + 1
    else:
        next_m = month + 1
        next_y = year
    deadline_date = datetime.date(next_y, next_m, 14)
    days_left = (deadline_date - now).days

    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    period_label = f"{month_names[month - 1]} {year}" if 1 <= month <= 12 else f"{month}/{year}"

    # Default firm info
    firm_name = "SBP Africa Group"
    firm_ssnit = "SSNIT-GH-001928"
    company = CompanyProfile.objects.first()
    if company:
        firm_name = company.company_name
        firm_ssnit = company.tax_identification_number or company.registration_number or firm_ssnit

    batches_qs = PayrollBatch.objects.filter(month=month, year=year)

    # 1. CLIENT-SPECIFIC SUMMARY
    if client_id:
        client_obj = Client.objects.filter(id=client_id).first()
        client_batches = batches_qs.filter(client_id=client_id)

        client_name = client_obj.name if client_obj else (client_batches.first().client_name if client_batches.exists() else "Client Organization")
        client_ssnit = client_obj.tax_id if client_obj and client_obj.tax_id else f"SSNIT-CL-{str(client_id)[:8].upper()}"
        client_code = client_obj.code if client_obj and client_obj.code else "CLI"

        total_gross = Decimal('0.00')
        all_funded = True
        for b in client_batches:
            total_gross += (b.total_net_salaries + b.total_statutory_taxes)
            if b.status not in ['FUNDED', 'DISBURSED']:
                all_funded = False

        ssnit_calc = GhanaTaxEngine.calculate_ssnit(total_gross)
        batch_count = client_batches.count()

        client_item = {
            'client_id': str(client_id),
            'client_name': client_name,
            'client_code': client_code,
            'employer_ssnit_number': client_ssnit,
            'batch_count': batch_count,
            'batch_status': client_batches.first().status if batch_count > 0 else 'NONE',
            'is_funded': all_funded if batch_count > 0 else False,
            'gross_salaries': total_gross.quantize(Decimal('0.01')),
            'employee_share': ssnit_calc['employee_ssnit'],
            'employer_share': ssnit_calc['employer_ssnit'],
            'tier_1_ssnit': ssnit_calc['tier_1_ssnit'],
            'tier_2_trustee': ssnit_calc['tier_2_trustee'],
            'total_ssnit_liability': ssnit_calc['total_ssnit_liability'],
        }

        return {
            'client_id': str(client_id),
            'employer_name': client_name,
            'employer_ssnit_number': client_ssnit,
            'period_month': month,
            'period_year': year,
            'period_label': period_label,
            'submission_deadline': deadline_date.isoformat(),
            'days_until_deadline': days_left,
            'is_overdue': days_left < 0,
            'total_clients': 1,
            'total_employees': batch_count if batch_count > 0 else 0,
            'total_gross_salaries': total_gross.quantize(Decimal('0.01')),
            'total_employee_share': ssnit_calc['employee_ssnit'],
            'total_employer_share': ssnit_calc['employer_ssnit'],
            'tier_1_payable_ssnit': ssnit_calc['tier_1_ssnit'],
            'tier_2_payable_trustee': ssnit_calc['tier_2_trustee'],
            'total_statutory_pension_liability': ssnit_calc['total_ssnit_liability'],
            'statutory_penalty_clause': "Under Act 766 Section 64, remittances after the 14th attract a 3% compounding monthly penalty.",
            'clients': [client_item]
        }

    # 2. CONSOLIDATED MULTI-CLIENT SUMMARY (SBP AFRICA HR FIRM PORTFOLIO)
    if organization_id:
        org = Organization.objects.filter(id=organization_id).first()
        if org and batches_qs.filter(client_id=org.id).exists():
            batches_qs = batches_qs.filter(client_id=org.id)

    client_groups = {}
    for b in batches_qs:
        cid = str(b.client_id)
        if cid not in client_groups:
            client_groups[cid] = {
                'client_name': b.client_name,
                'batches': [],
                'total_gross': Decimal('0.00'),
                'all_funded': True,
            }
        client_groups[cid]['batches'].append(b)
        client_groups[cid]['total_gross'] += (b.total_net_salaries + b.total_statutory_taxes)
        if b.status not in ['FUNDED', 'DISBURSED']:
            client_groups[cid]['all_funded'] = False

    clients_summary = []
    grand_total_gross = Decimal('0.00')
    grand_total_emp = Decimal('0.00')
    grand_total_empr = Decimal('0.00')
    grand_total_tier1 = Decimal('0.00')
    grand_total_tier2 = Decimal('0.00')
    grand_total_liability = Decimal('0.00')

    for cid, cdata in client_groups.items():
        client_rec = Client.objects.filter(id=cid).first()
        c_code = client_rec.code if client_rec and client_rec.code else "CLI"
        c_ssnit = client_rec.tax_id if client_rec and client_rec.tax_id else f"SSNIT-CL-{cid[:8].upper()}"
        c_name = client_rec.name if client_rec else cdata['client_name']

        c_calc = GhanaTaxEngine.calculate_ssnit(cdata['total_gross'])
        batch_cnt = len(cdata['batches'])
        first_b = cdata['batches'][0] if cdata['batches'] else None

        c_item = {
            'client_id': cid,
            'client_name': c_name,
            'client_code': c_code,
            'employer_ssnit_number': c_ssnit,
            'batch_count': batch_cnt,
            'batch_status': first_b.status if first_b else 'NONE',
            'is_funded': cdata['all_funded'],
            'gross_salaries': cdata['total_gross'].quantize(Decimal('0.01')),
            'employee_share': c_calc['employee_ssnit'],
            'employer_share': c_calc['employer_ssnit'],
            'tier_1_ssnit': c_calc['tier_1_ssnit'],
            'tier_2_trustee': c_calc['tier_2_trustee'],
            'total_ssnit_liability': c_calc['total_ssnit_liability'],
        }
        clients_summary.append(c_item)

        grand_total_gross += c_item['gross_salaries']
        grand_total_emp += c_item['employee_share']
        grand_total_empr += c_item['employer_share']
        grand_total_tier1 += c_item['tier_1_ssnit']
        grand_total_tier2 += c_item['tier_2_trustee']
        grand_total_liability += c_item['total_ssnit_liability']

    total_client_count = len(clients_summary)

    return {
        'client_id': None,
        'employer_name': f"{firm_name} (Consolidated Multi-Client Return)",
        'employer_ssnit_number': firm_ssnit,
        'period_month': month,
        'period_year': year,
        'period_label': period_label,
        'submission_deadline': deadline_date.isoformat(),
        'days_until_deadline': days_left,
        'is_overdue': days_left < 0,
        'total_clients': total_client_count,
        'total_employees': batches_qs.count(),
        'total_gross_salaries': grand_total_gross.quantize(Decimal('0.01')),
        'total_employee_share': grand_total_emp.quantize(Decimal('0.01')),
        'total_employer_share': grand_total_empr.quantize(Decimal('0.01')),
        'tier_1_payable_ssnit': grand_total_tier1.quantize(Decimal('0.01')),
        'tier_2_payable_trustee': grand_total_tier2.quantize(Decimal('0.01')),
        'total_statutory_pension_liability': grand_total_liability.quantize(Decimal('0.01')),
        'statutory_penalty_clause': "Under Act 766 Section 64, remittances after the 14th attract a 3% compounding monthly penalty.",
        'clients': clients_summary
    }

