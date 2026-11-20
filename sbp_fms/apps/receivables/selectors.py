from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key, KEY_AGING_REPORT
from apps.common.filters import apply_dict_filters, merge_filters
from .models import Client, ClientInvoice, ClientInvoiceStatus


def client_list(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> list[Client]:
    combined_filters = merge_filters(filters, country_code=country_code)
    cache_key = make_cache_key('fms:clients:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Client.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def client_detail(*, client_id) -> Client:
    cache_key = f"fms:clients:detail:{client_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    client = get_object_or_404(Client, id=client_id)
    CacheManager.set(cache_key, client, timeout=1800)
    return client


def client_invoice_list(
    *,
    filters: Optional[dict] = None,
    client_id: Optional[str] = None,
    status: Optional[str] = None
) -> list[ClientInvoice]:
    combined_filters = merge_filters(filters, client_id=client_id, status=status)
    cache_key = make_cache_key('fms:receivables:invoices:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = ClientInvoice.objects.select_related('client').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def client_invoice_detail(*, invoice_id) -> ClientInvoice:
    cache_key = f"fms:receivables:invoices:detail:{invoice_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    inv = get_object_or_404(ClientInvoice.objects.select_related('client'), id=invoice_id)
    CacheManager.set(cache_key, inv, timeout=1800)
    return inv


def aging_report_get(*, filters: Optional[dict] = None, country_code: Optional[str] = None) -> dict:
    combined_filters = merge_filters(filters, country_code=country_code)
    target_country = combined_filters.get('country_code') or country_code or 'ALL'
    cache_key = KEY_AGING_REPORT.format(country=target_country)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    today = timezone.now().date()
    invoices = ClientInvoice.objects.filter(
        status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID, ClientInvoiceStatus.OVERDUE]
    )
    if target_country and target_country != 'ALL':
        invoices = invoices.filter(client__country_code=target_country)

    buckets = {
        'country_code': target_country,
        'current_0_30_days': Decimal('0'),
        'overdue_31_60_days': Decimal('0'),
        'overdue_61_90_days': Decimal('0'),
        'overdue_90_plus_days': Decimal('0'),
        'total_receivables': Decimal('0')
    }

    for inv in invoices:
        bal = inv.balance_due
        days_overdue = (today - inv.due_date).days
        buckets['total_receivables'] += bal

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


from .models import PaymentReceipt, PaymentReceiptStatus


def payment_receipt_list(
    *,
    filters: Optional[dict] = None,
    client_id: Optional[str] = None,
    status: Optional[str] = None
) -> list[PaymentReceipt]:
    combined_filters = merge_filters(filters, client_id=client_id, status=status)
    cache_key = make_cache_key('fms:receivables:receipts:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = PaymentReceipt.objects.select_related('client', 'bank_account').prefetch_related('allocations__invoice').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def payment_receipt_detail(*, receipt_id) -> PaymentReceipt:
    cache_key = f"fms:receivables:receipts:detail:{receipt_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    receipt = get_object_or_404(
        PaymentReceipt.objects.select_related('client', 'bank_account').prefetch_related('allocations__invoice'),
        id=receipt_id
    )
    CacheManager.set(cache_key, receipt, timeout=1800)
    return receipt


def customer_statement_get(*, client_id: str, date_from=None, date_to=None) -> dict:
    client = get_object_or_404(Client, id=client_id)
    invoices = ClientInvoice.objects.filter(client=client)
    receipts = PaymentReceipt.objects.filter(client=client, status=PaymentReceiptStatus.CONFIRMED)

    if date_from:
        invoices = invoices.filter(issue_date__gte=date_from)
        receipts = receipts.filter(receipt_date__gte=date_from)
    if date_to:
        invoices = invoices.filter(issue_date__lte=date_to)
        receipts = receipts.filter(receipt_date__lte=date_to)

    ledger_entries = []
    running_bal = Decimal('0.0000')

    for inv in invoices:
        running_bal += inv.total_amount
        ledger_entries.append({
            'date': str(inv.issue_date),
            'reference': inv.invoice_number,
            'type': 'INVOICE',
            'billed': inv.total_amount,
            'received': Decimal('0.0000'),
            'balance': running_bal
        })

    for rec in receipts:
        running_bal -= rec.amount_received
        ledger_entries.append({
            'date': str(rec.receipt_date),
            'reference': rec.receipt_number,
            'type': 'RECEIPT',
            'billed': Decimal('0.0000'),
            'received': rec.amount_received,
            'balance': running_bal
        })

    ledger_entries.sort(key=lambda x: x['date'])

    return {
        'client_id': str(client.id),
        'client_name': client.name,
        'client_code': client.code,
        'country_code': client.country_code,
        'closing_balance': running_bal,
        'transactions': ledger_entries
    }


def client_invoice_template_list(*, client_id: Optional[str] = None) -> list:
    from .models import ClientInvoiceTemplate
    qs = ClientInvoiceTemplate.objects.filter(is_active=True)
    if client_id:
        from django.db.models import Q
        qs = qs.filter(Q(client_id=client_id) | Q(client__isnull=True))
    return list(qs.order_by('-is_default', 'template_name'))


def client_invoice_template_detail(*, template_id):
    from .models import ClientInvoiceTemplate
    return get_object_or_404(ClientInvoiceTemplate, id=template_id)


def invoice_template_presets_list() -> list[dict]:
    from .presets import INVOICE_PRESETS
    return INVOICE_PRESETS


def client_invoice_render_data(*, invoice_id) -> dict:
    from .models import ClientInvoice, ClientInvoiceTemplate
    from .presets import get_preset_by_code
    from apps.ledger.models import CompanyProfile
    from apps.treasury.models import BankAccount

    inv = get_object_or_404(
        ClientInvoice.objects.select_related('client', 'template').prefetch_related('lines'),
        id=invoice_id
    )

    client = inv.client
    template = inv.template
    if not template and client.default_template:
        template = client.default_template
    if not template:
        template = ClientInvoiceTemplate.objects.filter(is_default=True).first()

    if template:
        layout_style = template.layout_style
        primary_color = template.primary_color
        secondary_color = template.secondary_color
        accent_color = template.accent_color
        font_family = template.font_family
        invoice_title = template.invoice_title
        show_logo = template.show_logo
        logo_url = template.logo_url
        show_tax_breakdown = template.show_tax_breakdown
        show_bank_details = template.show_bank_details
        show_due_date_badge = template.show_due_date_badge
        show_discount = template.show_discount
        show_unit_of_measure = template.show_unit_of_measure
        notes = inv.notes or template.default_notes
        terms = inv.terms_and_conditions or template.default_terms
        footer_text = template.footer_text
        header_field_defs = template.header_custom_fields or template.custom_field_definitions or []
        line_field_defs = template.line_custom_fields or []
        template_id_str = str(template.id)
        template_name = template.template_name
    else:
        fallback = get_preset_by_code('STANDARD_CORPORATE') or {}
        layout_style = fallback.get('layout_style', 'CORPORATE')
        primary_color = fallback.get('primary_color', '#102a43')
        secondary_color = fallback.get('secondary_color', '#243b53')
        accent_color = fallback.get('accent_color', '#0ea5e9')
        font_family = fallback.get('font_family', 'Inter, sans-serif')
        invoice_title = fallback.get('invoice_title', 'TAX INVOICE')
        show_logo = True
        logo_url = ''
        show_tax_breakdown = True
        show_bank_details = True
        show_due_date_badge = True
        show_discount = True
        show_unit_of_measure = True
        notes = inv.notes or fallback.get('default_notes', 'Thank you for your business.')
        terms = inv.terms_and_conditions or fallback.get('default_terms', 'Payment due within terms.')
        footer_text = fallback.get('footer_text', 'SBP Africa Group')
        header_field_defs = fallback.get('header_custom_fields', [])
        line_field_defs = fallback.get('line_custom_fields', [])
        template_id_str = None
        template_name = "Default Corporate Layout"

    # Format header custom fields
    inv_custom = inv.custom_fields or {}
    formatted_headers = []
    seen_keys = set()
    for f in header_field_defs:
        k = f['key']
        seen_keys.add(k)
        val = inv_custom.get(k, f.get('default_value', ''))
        formatted_headers.append({
            'key': k,
            'label': f.get('label', k),
            'value': val,
            'type': f.get('type', 'text')
        })
    for k, v in inv_custom.items():
        if k not in seen_keys:
            formatted_headers.append({
                'key': k,
                'label': k.replace('_', ' ').title(),
                'value': v,
                'type': 'text'
            })

    # Format line items
    formatted_lines = []
    for l in inv.lines.all():
        line_custom = l.custom_fields or {}
        l_custom_formatted = []
        for lf in line_field_defs:
            lk = lf['key']
            l_custom_formatted.append({
                'key': lk,
                'label': lf.get('label', lk),
                'value': line_custom.get(lk, lf.get('default_value', ''))
            })
        for lk, lv in line_custom.items():
            if not any(x['key'] == lk for x in l_custom_formatted):
                l_custom_formatted.append({
                    'key': lk,
                    'label': lk.replace('_', ' ').title(),
                    'value': lv
                })

        formatted_lines.append({
            'id': str(l.id),
            'description': l.description,
            'quantity': l.quantity,
            'unit_of_measurement': l.unit_of_measurement,
            'unit_price': l.unit_price,
            'discount': l.discount,
            'tax_code': l.tax_code,
            'tax_rate': l.tax_rate,
            'tax_amount': l.tax_amount,
            'line_total': l.line_total,
            'custom_fields': line_custom,
            'custom_fields_formatted': l_custom_formatted
        })

    company = CompanyProfile.objects.first()
    company_data = {
        'company_name': company.company_name if company else "SBP Africa Group",
        'registration_number': company.registration_number if company else "",
        'tax_id': company.tax_identification_number if company else "C0019283921",
        'email': "finance@sbp-africa.com",
        'phone': "+233 30 291 0293",
        'address': company.registered_address if company else "Heritage Tower, Ridge, Accra, Ghana",
        'country_code': inv.client.country_code or 'GH'
    }

    bank_accounts = []
    if show_bank_details:
        for b in BankAccount.objects.filter(is_active=True)[:2]:
            bank_accounts.append({
                'bank_name': b.bank_name,
                'account_name': b.account_name,
                'account_number': b.account_number,
                'currency': b.currency,
                'swift_code': b.swift_bic,
                'branch': b.branch_name
            })

    return {
        'invoice': {
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'issue_date': str(inv.issue_date),
            'due_date': str(inv.due_date),
            'status': inv.status,
            'notes': notes,
            'terms_and_conditions': terms,
            'custom_fields': inv.custom_fields,
            'header_custom_fields': formatted_headers,
        },
        'client': {
            'id': str(client.id),
            'name': client.name,
            'code': client.code,
            'tax_id': client.tax_id,
            'registration_number': client.registration_number,
            'contact_person': client.contact_person,
            'email': client.email,
            'telephone': client.telephone,
            'billing_address': client.billing_address,
            'country_code': client.country_code
        },
        'company': company_data,
        'bank_accounts': bank_accounts,
        'template': {
            'id': template_id_str,
            'template_name': template_name,
            'layout_style': layout_style,
            'primary_color': primary_color,
            'secondary_color': secondary_color,
            'accent_color': accent_color,
            'font_family': font_family,
            'invoice_title': invoice_title,
            'show_logo': show_logo,
            'logo_url': logo_url,
            'show_tax_breakdown': show_tax_breakdown,
            'show_bank_details': show_bank_details,
            'show_due_date_badge': show_due_date_badge,
            'show_discount': show_discount,
            'show_unit_of_measure': show_unit_of_measure,
            'footer_text': footer_text,
            'line_column_definitions': line_field_defs
        },
        'totals': {
            'subtotal': inv.subtotal,
            'tax_amount': inv.tax_amount,
            'discount_amount': inv.discount_amount,
            'total_amount': inv.total_amount,
            'amount_paid': inv.amount_paid,
            'balance_due': inv.balance_due,
            'currency': 'GHS'
        },
        'lines': formatted_lines
    }


def invoice_builder_preview_data(*, template_data: dict, sample_invoice: Optional[dict] = None) -> dict:
    """
    Renders an interactive real-time preview of an invoice template configuration with custom fields.
    """
    sample = sample_invoice or {}
    layout_style = template_data.get('layout_style', 'MODERN')
    primary_color = template_data.get('primary_color', '#102a43')
    secondary_color = template_data.get('secondary_color', '#243b53')
    accent_color = template_data.get('accent_color', '#0ea5e9')
    font_family = template_data.get('font_family', 'Inter, sans-serif')
    invoice_title = template_data.get('invoice_title', 'TAX INVOICE')
    show_logo = template_data.get('show_logo', True)
    logo_url = template_data.get('logo_url', '')
    show_tax_breakdown = template_data.get('show_tax_breakdown', True)
    show_bank_details = template_data.get('show_bank_details', True)
    show_due_date_badge = template_data.get('show_due_date_badge', True)
    show_discount = template_data.get('show_discount', True)
    show_unit_of_measure = template_data.get('show_unit_of_measure', True)
    notes = sample.get('notes') or template_data.get('default_notes', 'Thank you for partnering with SBP Africa Group.')
    terms = sample.get('terms_and_conditions') or template_data.get('default_terms', 'Payment due within agreed payment terms.')
    footer_text = template_data.get('footer_text', 'SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg')

    header_defs = template_data.get('header_custom_fields') or template_data.get('custom_field_definitions') or []
    line_defs = template_data.get('line_custom_fields') or []

    # Format header fields
    sample_custom = sample.get('custom_fields', {})
    formatted_headers = []
    for f in header_defs:
        k = f['key']
        formatted_headers.append({
            'key': k,
            'label': f.get('label', k),
            'value': sample_custom.get(k, f.get('default_value') or f.get('placeholder') or "SAMPLE-VALUE"),
            'type': f.get('type', 'text')
        })

    # Sample line items
    sample_lines_input = sample.get('lines', [])
    if not sample_lines_input:
        sample_lines_input = [
            {
                'description': 'Outsourced Workforce - Heavy Machinery Operations (Batch 1)',
                'quantity': Decimal('26.00'),
                'unit_of_measurement': 'Days',
                'unit_price': Decimal('450.0000'),
                'discount': Decimal('0.0000'),
                'tax_code': 'VAT-STANDARD',
                'tax_rate': Decimal('0.1500'),
                'tax_amount': Decimal('1755.0000'),
                'line_total': Decimal('13455.0000'),
                'custom_fields': {
                    'staff_name': 'Kofi Mensah (ID: SBP-084)',
                    'role_designation': 'Excavator Operator',
                    'days_worked': 26,
                    'department': 'Tarkwa Pit A'
                }
            },
            {
                'description': 'Workforce Supervision & Occupational Safety Oversight',
                'quantity': Decimal('1.00'),
                'unit_of_measurement': 'Month',
                'unit_price': Decimal('8500.0000'),
                'discount': Decimal('500.0000'),
                'tax_code': 'VAT-STANDARD',
                'tax_rate': Decimal('0.1500'),
                'tax_amount': Decimal('1200.0000'),
                'line_total': Decimal('9200.0000'),
                'custom_fields': {
                    'staff_name': 'Kwesi Appiah',
                    'role_designation': 'HSE Specialist',
                    'days_worked': 30,
                    'department': 'HSE Mining'
                }
            }
        ]

    formatted_lines = []
    subtotal = Decimal('0.00')
    tax_total = Decimal('0.00')
    disc_total = Decimal('0.00')

    for idx, sl in enumerate(sample_lines_input, start=1):
        q = Decimal(str(sl.get('quantity', 1)))
        up = Decimal(str(sl.get('unit_price', 100)))
        d = Decimal(str(sl.get('discount', 0)))
        tr = Decimal(str(sl.get('tax_rate', 0.15)))
        line_sub = (q * up) - d
        line_tax = (line_sub * tr).quantize(Decimal('0.01'))
        line_tot = line_sub + line_tax

        subtotal += line_sub
        tax_total += line_tax
        disc_total += d

        sc_fields = sl.get('custom_fields', {})
        sc_formatted = []
        for lf in line_defs:
            lk = lf['key']
            sc_formatted.append({
                'key': lk,
                'label': lf.get('label', lk),
                'value': sc_fields.get(lk, lf.get('default_value') or lf.get('placeholder') or "")
            })

        formatted_lines.append({
            'id': f"sample-line-{idx}",
            'description': sl.get('description', f"Service Item {idx}"),
            'quantity': q,
            'unit_of_measurement': sl.get('unit_of_measurement', 'Unit'),
            'unit_price': up,
            'discount': d,
            'tax_code': sl.get('tax_code', 'VAT-15'),
            'tax_rate': tr,
            'tax_amount': line_tax,
            'line_total': line_tot,
            'custom_fields': sc_fields,
            'custom_fields_formatted': sc_formatted
        })

    grand_total = subtotal + tax_total

    return {
        'invoice': {
            'id': 'preview-sample-uuid',
            'invoice_number': sample.get('invoice_number', 'INV-PREVIEW-2026-001'),
            'issue_date': str(sample.get('issue_date', '2026-10-31')),
            'due_date': str(sample.get('due_date', '2026-11-30')),
            'status': 'PREVIEW',
            'notes': notes,
            'terms_and_conditions': terms,
            'custom_fields': sample_custom,
            'header_custom_fields': formatted_headers,
        },
        'client': {
            'id': 'preview-client-uuid',
            'name': sample.get('client_name', 'Ashanti Gold Mining Consortium'),
            'code': 'AGMC',
            'tax_id': 'TIN-GH-8291039',
            'registration_number': 'CS-829102-GH',
            'contact_person': 'Kwame Antwi (Finance & Procurement)',
            'email': 'procurement@ashantigold.com',
            'telephone': '+233 31 209 1029',
            'billing_address': 'Plot 4A Mining Concession, Tarkwa, Western Region, Ghana',
            'country_code': 'GH'
        },
        'company': {
            'company_name': "SBP Africa Group",
            'registration_number': "CS-001928-GH",
            'tax_id': "C0019283921",
            'email': "finance@sbp-africa.com",
            'phone': "+233 30 291 0293",
            'address': "Heritage Tower, Ridge, Accra, Ghana",
            'country_code': 'GH'
        },
        'bank_accounts': [
            {
                'bank_name': 'GCB Bank PLC',
                'account_name': 'SBP Africa Group Operations',
                'account_number': '1011122334455',
                'currency': 'GHS',
                'swift_code': 'GCBLGHAC',
                'branch': 'High Street Commercial Branch'
            }
        ] if show_bank_details else [],
        'template': {
            'id': template_data.get('id', 'builder-live-preview'),
            'template_name': template_data.get('template_name', 'Custom Builder Configuration'),
            'layout_style': layout_style,
            'primary_color': primary_color,
            'secondary_color': secondary_color,
            'accent_color': accent_color,
            'font_family': font_family,
            'invoice_title': invoice_title,
            'show_logo': show_logo,
            'logo_url': logo_url,
            'show_tax_breakdown': show_tax_breakdown,
            'show_bank_details': show_bank_details,
            'show_due_date_badge': show_due_date_badge,
            'show_discount': show_discount,
            'show_unit_of_measure': show_unit_of_measure,
            'footer_text': footer_text,
            'line_column_definitions': line_defs
        },
        'totals': {
            'subtotal': subtotal.quantize(Decimal('0.01')),
            'tax_amount': tax_total.quantize(Decimal('0.01')),
            'discount_amount': disc_total.quantize(Decimal('0.01')),
            'total_amount': grand_total.quantize(Decimal('0.01')),
            'amount_paid': Decimal('0.00'),
            'balance_due': grand_total.quantize(Decimal('0.01')),
            'currency': 'GHS'
        },
        'lines': formatted_lines
    }

