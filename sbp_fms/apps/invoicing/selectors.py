from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db.models import QuerySet, Q
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from apps.invoicing.models import (
    InvoiceCategory,
    InvoiceTemplate,
    BillableItem,
    Invoice,
    RecurringSchedule,
)
from apps.invoicing.presets import get_template_presets_list, get_preset_by_code
from apps.ledger.models import CompanyProfile


class InvoicingSelector:
    @staticmethod
    def invoice_category_list(*, is_active: Optional[bool] = None, search: Optional[str] = None) -> List[InvoiceCategory]:
        filters = {'is_active': is_active, 'search': search}
        cache_key = make_cache_key('fms:invoicing:categories:list', filters=filters)
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        qs = InvoiceCategory.objects.all().select_related('income_account')
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search))
        results = list(qs.order_by('name'))
        CacheManager.set(cache_key, results, timeout=1800)
        return results

    @staticmethod
    def invoice_category_detail(*, category_id: str) -> InvoiceCategory:
        cache_key = f"fms:invoicing:category:detail:{category_id}"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        category = get_object_or_404(InvoiceCategory.objects.select_related('income_account'), id=category_id)
        CacheManager.set(cache_key, category, timeout=1800)
        return category

    @staticmethod
    def invoice_template_list(*, client_id: Optional[str] = None, is_active: Optional[bool] = None) -> List[InvoiceTemplate]:
        filters = {'client_id': client_id, 'is_active': is_active}
        cache_key = make_cache_key('fms:invoicing:templates:list', filters=filters)
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        qs = InvoiceTemplate.objects.all().select_related('client')
        if client_id is not None:
            qs = qs.filter(Q(client_id=client_id) | Q(client__isnull=True))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        results = list(qs.order_by('-is_default', 'template_name'))
        CacheManager.set(cache_key, results, timeout=1800)
        return results

    @staticmethod
    def invoice_template_detail(*, template_id: str) -> InvoiceTemplate:
        cache_key = f"fms:invoicing:template:detail:{template_id}"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        template = get_object_or_404(InvoiceTemplate.objects.select_related('client'), id=template_id)
        CacheManager.set(cache_key, template, timeout=1800)
        return template

    @staticmethod
    def invoice_template_presets_list() -> list:
        cache_key = "fms:invoicing:presets:list"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        presets = get_template_presets_list()
        CacheManager.set(cache_key, presets, timeout=3600)
        return presets

    @staticmethod
    def billable_item_list(
        *,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> List[BillableItem]:
        filters = {'category_id': category_id, 'is_active': is_active, 'search': search}
        cache_key = make_cache_key('fms:invoicing:items:list', filters=filters)
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        qs = BillableItem.objects.all().select_related('category', 'income_account')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search))
        results = list(qs.order_by('code'))
        CacheManager.set(cache_key, results, timeout=1800)
        return results

    @staticmethod
    def billable_item_detail(*, item_id: str) -> BillableItem:
        cache_key = f"fms:invoicing:item:detail:{item_id}"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        item = get_object_or_404(BillableItem.objects.select_related('category', 'income_account'), id=item_id)
        CacheManager.set(cache_key, item, timeout=1800)
        return item

    @staticmethod
    def invoice_list(
        *,
        client_id: Optional[str] = None,
        category_id: Optional[str] = None,
        status: Optional[str] = None,
        invoice_type: Optional[str] = None,
        start_date=None,
        end_date=None,
        search: Optional[str] = None
    ) -> List[Invoice]:
        filters = {
            'client_id': client_id,
            'category_id': category_id,
            'status': status,
            'invoice_type': invoice_type,
            'start_date': str(start_date) if start_date else None,
            'end_date': str(end_date) if end_date else None,
            'search': search,
        }
        cache_key = make_cache_key('fms:invoicing:invoices:list', filters=filters)
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        qs = Invoice.objects.all().select_related('client', 'category', 'template', 'created_by', 'approved_by')
        if client_id:
            qs = qs.filter(client_id=client_id)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if status:
            qs = qs.filter(status=status)
        if invoice_type:
            qs = qs.filter(invoice_type=invoice_type)
        if start_date:
            qs = qs.filter(issue_date__gte=start_date)
        if end_date:
            qs = qs.filter(issue_date__lte=end_date)
        if search:
            qs = qs.filter(
                Q(invoice_number__icontains=search)
                | Q(reference_number__icontains=search)
                | Q(description__icontains=search)
                | Q(client__name__icontains=search)
            )
        results = list(qs.order_by('-issue_date', '-created_at'))
        CacheManager.set(cache_key, results, timeout=1800)
        return results

    @staticmethod
    def invoice_detail(*, invoice_id: str) -> Invoice:
        cache_key = f"fms:invoicing:invoice:detail:{invoice_id}"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        invoice = get_object_or_404(
            Invoice.objects.select_related('client', 'category', 'template', 'journal_entry', 'parent_invoice')
            .prefetch_related('lines', 'lines__item', 'tax_lines', 'delivery_logs'),
            id=invoice_id
        )
        CacheManager.set(cache_key, invoice, timeout=1800)
        return invoice

    @staticmethod
    def invoice_render_data(*, invoice_id: str) -> Dict[str, Any]:
        """
        Gathers complete hierarchical data to render or export an invoice
        with branding, custom fields, lines, and statutory tax breakdown.
        Results are cached for performance.
        """
        cache_key = f"fms:invoicing:render:{invoice_id}"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        invoice = InvoicingSelector.invoice_detail(invoice_id=invoice_id)
        template = invoice.template or InvoiceTemplate.objects.filter(is_default=True).first()

        # Company profile defaults
        company_profile = CompanyProfile.objects.first()
        company_info = {
            'name': (getattr(company_profile, 'company_name', '') or 'SBP Africa Group'),
            'legal_name': (getattr(company_profile, 'company_name', '') or 'SBP Africa Group Ltd'),
            'tax_number': (getattr(company_profile, 'tax_identification_number', '') or 'C0001234567'),
            'email': (getattr(company_profile, 'email', '') or 'invoicing@sbp-africa.com'),
            'phone': (getattr(company_profile, 'telephone', '') or '+233 302 000 000'),
            'address': (getattr(company_profile, 'business_address', '') or 'Airport Residential Area, Accra, Ghana'),
            'logo_url': getattr(company_profile, 'logo_url', ''),
        }

        # Template configurations
        template_config = {
            'layout_style': getattr(template, 'layout_style', 'MODERN'),
            'primary_color': getattr(template, 'primary_color', '#102a43'),
            'secondary_color': getattr(template, 'secondary_color', '#243b53'),
            'accent_color': getattr(template, 'accent_color', '#0ea5e9'),
            'logo_url': getattr(template, 'logo_url', '') or company_info['logo_url'],
            'show_logo': getattr(template, 'show_logo', True),
            'font_family': getattr(template, 'font_family', 'Inter, sans-serif'),
            'invoice_title': getattr(template, 'invoice_title', 'TAX INVOICE'),
            'show_tax_breakdown': getattr(template, 'show_tax_breakdown', True),
            'show_bank_details': getattr(template, 'show_bank_details', True),
            'show_due_date_badge': getattr(template, 'show_due_date_badge', True),
            'show_discount': getattr(template, 'show_discount', True),
            'show_unit_of_measure': getattr(template, 'show_unit_of_measure', True),
            'header_custom_fields': getattr(template, 'header_custom_fields', []),
            'line_custom_fields': getattr(template, 'line_custom_fields', []),
        }

        # Client info
        client = invoice.client
        client_info = {
            'id': str(client.id),
            'name': client.name,
            'code': getattr(client, 'code', ''),
            'email': getattr(client, 'email', ''),
            'phone': getattr(client, 'phone', ''),
            'address': getattr(client, 'billing_address', getattr(client, 'address', '')),
            'tin': getattr(client, 'tin', getattr(client, 'tax_number', '')),
        }

        # Lines formatting
        lines_data = []
        for line in invoice.lines.all():
            lines_data.append({
                'id': str(line.id),
                'item_code': line.item.code if line.item else None,
                'description': line.description,
                'quantity': float(line.quantity),
                'unit_of_measurement': line.unit_of_measurement,
                'unit_price': float(line.unit_price),
                'discount_amount': float(line.discount_amount),
                'tax_code': line.tax_code,
                'tax_rate': float(line.tax_rate),
                'tax_amount': float(line.tax_amount),
                'line_total': float(line.line_total),
                'custom_fields': line.custom_fields,
            })

        # Tax lines formatting
        tax_lines_data = [
            {
                'tax_type': tl.tax_type,
                'rate': float(tl.rate),
                'base_amount': float(tl.base_amount),
                'tax_amount': float(tl.tax_amount),
            }
            for tl in invoice.tax_lines.all()
        ]

        # Banking Remittance Details
        banking_details = {
            'bank_name': 'Standard Chartered Bank Ghana PLC',
            'account_name': 'SBP Africa Operations Ltd',
            'account_number': '0100123456789',
            'branch': 'High Street Branch, Accra',
            'swift_code': 'SCBLGHAC',
            'mobile_money': 'MTN MoMo: 055 123 4567 (Merchant ID: 887123)',
        }

        render_payload = {
            'invoice_id': str(invoice.id),
            'invoice_number': invoice.invoice_number,
            'invoice_type': invoice.invoice_type,
            'category': {
                'id': str(invoice.category.id) if invoice.category else None,
                'code': invoice.category.code if invoice.category else None,
                'name': invoice.category.name if invoice.category else None,
            } if invoice.category else None,
            'description': invoice.description,
            'status': invoice.status,
            'currency': invoice.currency,
            'exchange_rate': float(invoice.exchange_rate),
            'issue_date': invoice.issue_date.isoformat(),
            'due_date': invoice.due_date.isoformat(),
            'billing_period_start': invoice.billing_period_start.isoformat() if invoice.billing_period_start else None,
            'billing_period_end': invoice.billing_period_end.isoformat() if invoice.billing_period_end else None,
            'reference_number': invoice.reference_number,
            'subtotal': float(invoice.subtotal),
            'discount_amount': float(invoice.discount_amount),
            'tax_amount': float(invoice.tax_amount),
            'total_amount': float(invoice.total_amount),
            'amount_paid': float(invoice.amount_paid),
            'balance_due': float(invoice.balance_due),
            'custom_fields': invoice.custom_fields,
            'notes': invoice.notes or getattr(template, 'default_notes', ''),
            'terms_and_conditions': invoice.terms_and_conditions or getattr(template, 'default_terms', ''),
            'footer_text': invoice.footer_text or getattr(template, 'footer_text', ''),
            'company': company_info,
            'client': client_info,
            'template': template_config,
            'lines': lines_data,
            'tax_lines': tax_lines_data,
            'banking': banking_details,
        }

        CacheManager.set(cache_key, render_payload, timeout=3600)
        return render_payload

    @staticmethod
    def invoice_builder_preview_data(*, template_data: dict, sample_invoice: Optional[dict] = None) -> Dict[str, Any]:
        """
        Renders simulated live preview data for the interactive Invoice Builder canvas.
        """
        preset_code = template_data.get('preset_code')
        base_preset = get_preset_by_code(preset_code) if preset_code else {}

        merged_template = {
            'template_name': template_data.get('template_name', base_preset.get('template_name', 'Custom Template')),
            'layout_style': template_data.get('layout_style', base_preset.get('layout_style', 'MODERN')),
            'primary_color': template_data.get('primary_color', base_preset.get('primary_color', '#102a43')),
            'secondary_color': template_data.get('secondary_color', base_preset.get('secondary_color', '#243b53')),
            'accent_color': template_data.get('accent_color', base_preset.get('accent_color', '#0ea5e9')),
            'logo_url': template_data.get('logo_url', base_preset.get('logo_url', '')),
            'show_logo': template_data.get('show_logo', base_preset.get('show_logo', True)),
            'font_family': template_data.get('font_family', base_preset.get('font_family', 'Inter, sans-serif')),
            'invoice_title': template_data.get('invoice_title', base_preset.get('invoice_title', 'TAX INVOICE')),
            'show_tax_breakdown': template_data.get('show_tax_breakdown', base_preset.get('show_tax_breakdown', True)),
            'show_bank_details': template_data.get('show_bank_details', base_preset.get('show_bank_details', True)),
            'show_due_date_badge': template_data.get('show_due_date_badge', base_preset.get('show_due_date_badge', True)),
            'show_discount': template_data.get('show_discount', base_preset.get('show_discount', True)),
            'show_unit_of_measure': template_data.get('show_unit_of_measure', base_preset.get('show_unit_of_measure', True)),
            'default_notes': template_data.get('default_notes', base_preset.get('default_notes', 'Sample invoice terms and notes.')),
            'default_terms': template_data.get('default_terms', base_preset.get('default_terms', 'Net 30 days.')),
            'footer_text': template_data.get('footer_text', base_preset.get('footer_text', 'SBP Africa Group')),
            'header_custom_fields': template_data.get('header_custom_fields', base_preset.get('header_custom_fields', [])),
            'line_custom_fields': template_data.get('line_custom_fields', base_preset.get('line_custom_fields', [])),
        }

        # Build sample dummy invoice
        header_vals = {}
        for hf in merged_template['header_custom_fields']:
            header_vals[hf['key']] = hf.get('placeholder') or f"Sample {hf['label']}"

        sample_lines = [
            {
                'description': 'Outsourced Operational Staffing - Site Deployment',
                'quantity': 26.0,
                'unit_of_measurement': 'Days',
                'unit_price': 450.00,
                'discount_amount': 0.0,
                'tax_code': 'VAT_STANDARD',
                'tax_rate': 0.15,
                'tax_amount': 2562.30,
                'line_total': 11700.00,
                'custom_fields': {
                    lf['key']: lf.get('placeholder') or f"Sample {lf['label']}"
                    for lf in merged_template['line_custom_fields']
                }
            }
        ]

        return {
            'template': merged_template,
            'preview_invoice': {
                'invoice_number': 'INV-PREVIEW-001',
                'invoice_type': 'STANDARD',
                'category': {'name': 'Workforce & Staffing Outsourcing', 'code': 'WORKFORCE_OUTSOURCING'},
                'description': 'Monthly outsourced workforce and personnel deployment',
                'status': 'DRAFT',
                'currency': 'GHS',
                'issue_date': '2026-11-24',
                'due_date': '2026-12-24',
                'reference_number': 'PO-MINING-2026-PREVIEW',
                'subtotal': 11700.00,
                'tax_amount': 2562.30,
                'total_amount': 14262.30,
                'custom_fields': header_vals,
                'lines': sample_lines,
                'tax_lines': [
                    {'tax_type': 'NHIL (2.5%)', 'rate': 0.025, 'base_amount': 11700.00, 'tax_amount': 292.50},
                    {'tax_type': 'GETFund (2.5%)', 'rate': 0.025, 'base_amount': 11700.00, 'tax_amount': 292.50},
                    {'tax_type': 'COVID-19 Health Recovery (1.0%)', 'rate': 0.010, 'base_amount': 11700.00, 'tax_amount': 117.00},
                    {'tax_type': 'VAT (15.0%)', 'rate': 0.150, 'base_amount': 12402.00, 'tax_amount': 1860.30},
                ],
            }
        }

    @staticmethod
    def recurring_schedule_list(*, client_id: Optional[str] = None, status: Optional[str] = None) -> List[RecurringSchedule]:
        filters = {'client_id': client_id, 'status': status}
        cache_key = make_cache_key('fms:invoicing:schedules:list', filters=filters)
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        qs = RecurringSchedule.objects.all().select_related('client', 'template', 'category')
        if client_id:
            qs = qs.filter(client_id=client_id)
        if status:
            qs = qs.filter(status=status)
        results = list(qs.order_by('next_run_date'))
        CacheManager.set(cache_key, results, timeout=1800)
        return results

    @staticmethod
    def recurring_schedule_detail(*, schedule_id: str) -> RecurringSchedule:
        cache_key = f"fms:invoicing:schedule:detail:{schedule_id}"
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached

        schedule = get_object_or_404(RecurringSchedule.objects.select_related('client', 'template', 'category'), id=schedule_id)
        CacheManager.set(cache_key, schedule, timeout=1800)
        return schedule
