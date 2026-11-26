import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.common.cache import CacheManager
from apps.invoicing.models import (
    InvoiceCategory,
    InvoiceType,
    InvoiceStatus,
    InvoiceLayoutStyle,
    InvoiceTemplate,
    BillableItem,
    Invoice,
    InvoiceLine,
    InvoiceTaxLine,
    RecurringSchedule,
    RecurringScheduleStatus,
    RecurringFrequency,
)
from apps.invoicing.presets import DEFAULT_INVOICE_CATEGORIES, get_preset_by_code
from apps.receivables.models import Client
from apps.ledger.models import Account, AccountType
from apps.ledger.services import LedgerService
from apps.taxation.engines import GhanaTaxEngine


def _get_or_create_account(code: str, name: str, acct_type: str, country_code: str = 'GH') -> Account:
    acct = Account.objects.filter(code=code).first()
    if not acct:
        acct, _ = Account.objects.get_or_create(
            code=code,
            defaults={'name': name, 'account_type': acct_type, 'currency': 'GHS', 'country_code': country_code}
        )
    return acct


class InvoicingService:

    # -------------------------------------------------------------------------
    # CATEGORY SERVICES (Dynamic Admin Managed)
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def invoice_category_create(
        *,
        name: str,
        code: str,
        description: str = '',
        income_account_id: Optional[str] = None,
        is_active: bool = True
    ) -> InvoiceCategory:
        code_clean = code.strip().upper().replace(' ', '_')
        if InvoiceCategory.objects.filter(code=code_clean).exists():
            raise ValidationError(f"Invoice Category with code '{code_clean}' already exists.")
        if InvoiceCategory.objects.filter(name__iexact=name.strip()).exists():
            raise ValidationError(f"Invoice Category with name '{name.strip()}' already exists.")

        income_account = None
        if income_account_id:
            income_account = Account.objects.filter(id=income_account_id).first()

        category = InvoiceCategory.objects.create(
            name=name.strip(),
            code=code_clean,
            description=description.strip(),
            income_account=income_account,
            is_system=False,
            is_active=is_active
        )
        CacheManager.invalidate_invoicing()
        return category

    @staticmethod
    @transaction.atomic
    def invoice_category_update(*, category_id: str, **fields) -> InvoiceCategory:
        category = InvoiceCategory.objects.get(id=category_id)
        if 'name' in fields:
            name_val = fields.pop('name').strip()
            if InvoiceCategory.objects.filter(name__iexact=name_val).exclude(id=category_id).exists():
                raise ValidationError(f"Invoice category with name '{name_val}' already exists.")
            category.name = name_val

        if 'code' in fields:
            code_val = fields.pop('code').strip().upper().replace(' ', '_')
            if InvoiceCategory.objects.filter(code=code_val).exclude(id=category_id).exists():
                raise ValidationError(f"Invoice category with code '{code_val}' already exists.")
            category.code = code_val

        if 'income_account_id' in fields:
            acct_id = fields.pop('income_account_id')
            category.income_account = Account.objects.filter(id=acct_id).first() if acct_id else None

        for k, v in fields.items():
            if hasattr(category, k):
                setattr(category, k, v)

        category.save()
        CacheManager.invalidate_invoicing()
        return category

    @staticmethod
    @transaction.atomic
    def invoice_category_delete(*, category_id: str) -> None:
        category = InvoiceCategory.objects.get(id=category_id)
        if category.is_system:
            raise ValidationError("System default invoice categories cannot be deleted.")
        if category.invoices.exists():
            raise ValidationError(f"Cannot delete category '{category.name}' because invoices are associated with it.")
        category.delete()
        CacheManager.invalidate_invoicing()

    @staticmethod
    @transaction.atomic
    def invoice_category_seed_defaults() -> List[InvoiceCategory]:
        """
        Populates default SBP business vertical categories if they do not exist.
        """
        created_categories = []
        for cat_data in DEFAULT_INVOICE_CATEGORIES:
            cat, created = InvoiceCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data.get('description', ''),
                    'is_system': cat_data.get('is_system', False),
                    'is_active': True,
                }
            )
            created_categories.append(cat)
        CacheManager.invalidate_invoicing()
        return created_categories

    # -------------------------------------------------------------------------
    # TEMPLATE SERVICES (Builder Engine)
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def invoice_template_create(
        *,
        template_name: str,
        layout_style: str = InvoiceLayoutStyle.MODERN,
        client_id: Optional[str] = None,
        preset_code: str = '',
        primary_color: str = '#102a43',
        secondary_color: str = '#243b53',
        accent_color: str = '#0ea5e9',
        logo_url: str = '',
        show_logo: bool = True,
        font_family: str = 'Inter, sans-serif',
        invoice_title: str = 'TAX INVOICE',
        show_tax_breakdown: bool = True,
        show_bank_details: bool = True,
        show_due_date_badge: bool = True,
        show_discount: bool = True,
        show_unit_of_measure: bool = True,
        default_notes: str = '',
        default_terms: str = '',
        footer_text: str = '',
        header_custom_fields: Optional[List[Dict[str, Any]]] = None,
        line_custom_fields: Optional[List[Dict[str, Any]]] = None,
        is_default: bool = False
    ) -> InvoiceTemplate:
        client = Client.objects.filter(id=client_id).first() if client_id else None

        if is_default:
            if client:
                InvoiceTemplate.objects.filter(client=client, is_default=True).update(is_default=False)
            else:
                InvoiceTemplate.objects.filter(client__isnull=True, is_default=True).update(is_default=False)

        template = InvoiceTemplate.objects.create(
            template_name=template_name.strip(),
            preset_code=preset_code.strip(),
            client=client,
            layout_style=layout_style,
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
            logo_url=logo_url,
            show_logo=show_logo,
            font_family=font_family,
            invoice_title=invoice_title,
            show_tax_breakdown=show_tax_breakdown,
            show_bank_details=show_bank_details,
            show_due_date_badge=show_due_date_badge,
            show_discount=show_discount,
            show_unit_of_measure=show_unit_of_measure,
            default_notes=default_notes,
            default_terms=default_terms,
            footer_text=footer_text,
            header_custom_fields=header_custom_fields or [],
            line_custom_fields=line_custom_fields or [],
            is_default=is_default,
            is_active=True,
        )
        CacheManager.invalidate_invoicing()
        return template

    @staticmethod
    @transaction.atomic
    def invoice_template_update(*, template_id: str, **fields) -> InvoiceTemplate:
        template = InvoiceTemplate.objects.get(id=template_id)
        if fields.get('is_default'):
            if template.client:
                InvoiceTemplate.objects.filter(client=template.client, is_default=True).exclude(id=template_id).update(is_default=False)
            else:
                InvoiceTemplate.objects.filter(client__isnull=True, is_default=True).exclude(id=template_id).update(is_default=False)

        for k, v in fields.items():
            if hasattr(template, k):
                setattr(template, k, v)

        template.save()
        CacheManager.invalidate_invoicing()
        return template

    @staticmethod
    @transaction.atomic
    def invoice_template_delete(*, template_id: str) -> None:
        template = InvoiceTemplate.objects.get(id=template_id)
        if template.invoices.exists():
            raise ValidationError(f"Cannot delete template '{template.template_name}' because it has issued invoices.")
        template.delete()
        CacheManager.invalidate_invoicing()

    @staticmethod
    @transaction.atomic
    def invoice_template_apply_preset(
        *,
        preset_code: str,
        client_id: Optional[str] = None,
        template_name: Optional[str] = None,
        make_default: bool = False
    ) -> InvoiceTemplate:
        preset_data = get_preset_by_code(preset_code)
        name = template_name or preset_data['template_name']

        return InvoicingService.invoice_template_create(
            template_name=name,
            layout_style=preset_data['layout_style'],
            client_id=client_id,
            preset_code=preset_code,
            primary_color=preset_data['primary_color'],
            secondary_color=preset_data['secondary_color'],
            accent_color=preset_data['accent_color'],
            invoice_title=preset_data['invoice_title'],
            show_tax_breakdown=preset_data.get('show_tax_breakdown', True),
            show_bank_details=preset_data.get('show_bank_details', True),
            show_due_date_badge=preset_data.get('show_due_date_badge', True),
            show_discount=preset_data.get('show_discount', True),
            show_unit_of_measure=preset_data.get('show_unit_of_measure', True),
            default_notes=preset_data.get('default_notes', ''),
            default_terms=preset_data.get('default_terms', ''),
            footer_text=preset_data.get('footer_text', ''),
            header_custom_fields=preset_data.get('header_custom_fields', []),
            line_custom_fields=preset_data.get('line_custom_fields', []),
            is_default=make_default,
        )

    # -------------------------------------------------------------------------
    # BILLABLE ITEM SERVICES
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def billable_item_create(
        *,
        code: str,
        name: str,
        category_id: Optional[str] = None,
        description: str = '',
        default_unit: str = 'Unit',
        default_unit_price: Decimal = Decimal('0.00'),
        default_tax_code: str = 'VAT_STANDARD',
        default_tax_rate: Decimal = Decimal('0.15'),
        income_account_id: Optional[str] = None,
        is_active: bool = True
    ) -> BillableItem:
        code_clean = code.strip().upper()
        if BillableItem.objects.filter(code=code_clean).exists():
            raise ValidationError(f"Billable item with code '{code_clean}' already exists.")

        category = InvoiceCategory.objects.filter(id=category_id).first() if category_id else None
        income_account = Account.objects.filter(id=income_account_id).first() if income_account_id else None

        item = BillableItem.objects.create(
            code=code_clean,
            name=name.strip(),
            category=category,
            description=description.strip(),
            default_unit=default_unit.strip(),
            default_unit_price=Decimal(str(default_unit_price)),
            default_tax_code=default_tax_code.strip(),
            default_tax_rate=Decimal(str(default_tax_rate)),
            income_account=income_account,
            is_active=is_active
        )
        CacheManager.invalidate_invoicing()
        return item

    @staticmethod
    @transaction.atomic
    def billable_item_update(*, item_id: str, **fields) -> BillableItem:
        item = BillableItem.objects.get(id=item_id)
        if 'code' in fields:
            code_val = fields.pop('code').strip().upper()
            if BillableItem.objects.filter(code=code_val).exclude(id=item_id).exists():
                raise ValidationError(f"Billable item with code '{code_val}' already exists.")
            item.code = code_val

        if 'category_id' in fields:
            cat_id = fields.pop('category_id')
            item.category = InvoiceCategory.objects.filter(id=cat_id).first() if cat_id else None

        if 'income_account_id' in fields:
            acct_id = fields.pop('income_account_id')
            item.income_account = Account.objects.filter(id=acct_id).first() if acct_id else None

        for k, v in fields.items():
            if hasattr(item, k):
                setattr(item, k, v)

        item.save()
        CacheManager.invalidate_invoicing()
        return item

    @staticmethod
    @transaction.atomic
    def billable_item_delete(*, item_id: str) -> None:
        item = BillableItem.objects.get(id=item_id)
        if item.invoice_lines.exists():
            raise ValidationError(f"Cannot delete item '{item.name}' because it has been invoiced.")
        item.delete()
        CacheManager.invalidate_invoicing()

    # -------------------------------------------------------------------------
    # INVOICE CORE SERVICES
    # -------------------------------------------------------------------------
    @staticmethod
    def _generate_invoice_number(invoice_type: str) -> str:
        prefix = 'INV'
        if invoice_type == InvoiceType.PROFORMA:
            prefix = 'PRO'
        elif invoice_type == InvoiceType.CREDIT_NOTE:
            prefix = 'CN'
        elif invoice_type == InvoiceType.DEBIT_NOTE:
            prefix = 'DN'

        year = timezone.now().year
        count = Invoice.objects.filter(invoice_type=invoice_type, issue_date__year=year).count() + 1
        candidate = f"{prefix}-{year}-{count:04d}"
        while Invoice.objects.filter(invoice_number=candidate).exists():
            count += 1
            candidate = f"{prefix}-{year}-{count:04d}"
        return candidate

    @staticmethod
    @transaction.atomic
    def invoice_create(
        *,
        client_id: str,
        issue_date,
        due_date,
        invoice_type: str = InvoiceType.STANDARD,
        category_id: Optional[str] = None,
        description: str = '',
        template_id: Optional[str] = None,
        currency: str = 'GHS',
        exchange_rate: Decimal = Decimal('1.000000'),
        billing_period_start=None,
        billing_period_end=None,
        reference_number: str = '',
        invoice_number: Optional[str] = None,
        lines: List[Dict[str, Any]],
        custom_fields: Optional[Dict[str, Any]] = None,
        notes: str = '',
        terms_and_conditions: str = '',
        footer_text: str = '',
        auto_calculate_tax: bool = True,
        parent_invoice_id: Optional[str] = None,
        user=None,
    ) -> Invoice:
        client = Client.objects.get(id=client_id)
        if not lines:
            raise ValidationError("An invoice must contain at least one line item.")

        # Resolve category
        category = None
        if category_id:
            category = InvoiceCategory.objects.filter(id=category_id).first()

        # Resolve template
        template = None
        if template_id:
            template = InvoiceTemplate.objects.filter(id=template_id).first()
        if not template:
            template = InvoiceTemplate.objects.filter(client=client, is_default=True).first()
        if not template:
            template = InvoiceTemplate.objects.filter(client__isnull=True, is_default=True).first()

        # Validate required header custom fields defined on template
        custom_fields_data = custom_fields or {}
        if template and template.header_custom_fields:
            for field_def in template.header_custom_fields:
                if field_def.get('required') and not custom_fields_data.get(field_def['key']):
                    raise ValidationError(f"Required header field '{field_def['label']}' is missing.")

        # Determine invoice number
        inv_number = invoice_number or InvoicingService._generate_invoice_number(invoice_type)

        # Parent invoice (for Credit Note / Debit Note)
        parent_invoice = Invoice.objects.filter(id=parent_invoice_id).first() if parent_invoice_id else None

        invoice = Invoice.objects.create(
            invoice_number=inv_number,
            invoice_type=invoice_type,
            category=category,
            description=description.strip(),
            client=client,
            template=template,
            currency=currency.upper(),
            exchange_rate=Decimal(str(exchange_rate)),
            issue_date=issue_date,
            due_date=due_date,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            reference_number=reference_number.strip(),
            status=InvoiceStatus.DRAFT,
            custom_fields=custom_fields_data,
            notes=notes or getattr(template, 'default_notes', ''),
            terms_and_conditions=terms_and_conditions or getattr(template, 'default_terms', ''),
            footer_text=footer_text or getattr(template, 'footer_text', ''),
            parent_invoice=parent_invoice,
            created_by=user,
        )

        subtotal = Decimal('0.0000')
        total_discount = Decimal('0.0000')
        taxable_subtotal = Decimal('0.0000')

        line_objects = []
        for line_data in lines:
            item_id = line_data.get('item_id')
            item = BillableItem.objects.filter(id=item_id).first() if item_id else None

            qty = Decimal(str(line_data.get('quantity', 1.0)))
            unit_price = Decimal(str(line_data.get('unit_price', item.default_unit_price if item else 0.0)))
            discount = Decimal(str(line_data.get('discount_amount', 0.0)))
            desc = line_data.get('description') or (item.name if item else 'Service Item')
            uom = line_data.get('unit_of_measurement') or (item.default_unit if item else 'Unit')

            # Line custom fields validation
            line_cf = line_data.get('custom_fields', {})
            if template and template.line_custom_fields:
                for col_def in template.line_custom_fields:
                    if col_def.get('required') and not line_cf.get(col_def['key']):
                        raise ValidationError(f"Required line column '{col_def['label']}' missing in item '{desc}'.")

            raw_total = (qty * unit_price) - discount
            subtotal += raw_total
            total_discount += discount

            # Revenue account resolution
            rev_account = None
            if line_data.get('revenue_account_id'):
                rev_account = Account.objects.filter(id=line_data['revenue_account_id']).first()
            elif item and item.income_account:
                rev_account = item.income_account
            elif category and category.income_account:
                rev_account = category.income_account

            tax_code = line_data.get('tax_code', item.default_tax_code if item else 'VAT_STANDARD')
            tax_rate = Decimal(str(line_data.get('tax_rate', item.default_tax_rate if item else '0.1500')))

            # Check if this line is taxable
            if tax_code in ('VAT_STANDARD', 'TAXABLE'):
                taxable_subtotal += raw_total

            line_obj = InvoiceLine(
                invoice=invoice,
                item=item,
                description=desc,
                quantity=qty,
                unit_of_measurement=uom,
                unit_price=unit_price,
                discount_amount=discount,
                tax_code=tax_code,
                tax_rate=tax_rate,
                tax_amount=Decimal('0.0000'),
                line_total=raw_total,
                custom_fields=line_cf,
                revenue_account=rev_account,
            )
            line_objects.append(line_obj)

        InvoiceLine.objects.bulk_create(line_objects)

        # Statutory Ghana Tax Breakdown
        total_tax = Decimal('0.0000')
        tax_line_objects = []

        if auto_calculate_tax and taxable_subtotal > Decimal('0.0000'):
            # Ghana GRA Statutory Indirect Tax Cascading
            tax_calc = GhanaTaxEngine.calculate_ghana_indirect_tax(taxable_subtotal, include_covid_levy=True)
            nhil_amt = tax_calc['nhil_amount']
            getfund_amt = tax_calc['getfund_amount']
            covid_amt = tax_calc['covid_levy_amount']
            vat_amt = tax_calc['vat_amount']
            total_tax = tax_calc['total_tax']

            tax_line_objects = [
                InvoiceTaxLine(
                    invoice=invoice,
                    tax_type='NHIL (2.5%)',
                    rate=Decimal('0.0250'),
                    base_amount=taxable_subtotal,
                    tax_amount=nhil_amt,
                ),
                InvoiceTaxLine(
                    invoice=invoice,
                    tax_type='GETFund (2.5%)',
                    rate=Decimal('0.0250'),
                    base_amount=taxable_subtotal,
                    tax_amount=getfund_amt,
                ),
                InvoiceTaxLine(
                    invoice=invoice,
                    tax_type='COVID-19 Health Recovery (1.0%)',
                    rate=Decimal('0.0100'),
                    base_amount=taxable_subtotal,
                    tax_amount=covid_amt,
                ),
                InvoiceTaxLine(
                    invoice=invoice,
                    tax_type='VAT (15.0%)',
                    rate=Decimal('0.1500'),
                    base_amount=tax_calc['vat_base'],
                    tax_amount=vat_amt,
                ),
            ]
            InvoiceTaxLine.objects.bulk_create(tax_line_objects)

        invoice.subtotal = subtotal
        invoice.discount_amount = total_discount
        invoice.tax_amount = total_tax
        invoice.total_amount = subtotal + total_tax
        invoice.save()

        # Invalidate Caches
        CacheManager.invalidate_invoicing()
        CacheManager.invalidate_receivables()

        return invoice

    @staticmethod
    @transaction.atomic
    def invoice_update(*, invoice_id: str, **fields) -> Invoice:
        invoice = Invoice.objects.get(id=invoice_id)
        if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.PENDING_APPROVAL):
            raise ValidationError(f"Cannot edit invoice in '{invoice.status}' status.")

        if 'category_id' in fields:
            cat_id = fields.pop('category_id')
            invoice.category = InvoiceCategory.objects.filter(id=cat_id).first() if cat_id else None

        if 'template_id' in fields:
            tmpl_id = fields.pop('template_id')
            invoice.template = InvoiceTemplate.objects.filter(id=tmpl_id).first() if tmpl_id else None

        for k, v in fields.items():
            if hasattr(invoice, k):
                setattr(invoice, k, v)

        invoice.save()
        CacheManager.invalidate_invoicing()
        CacheManager.invalidate_receivables()
        return invoice

    @staticmethod
    @transaction.atomic
    def invoice_approve(*, invoice_id: str, user=None) -> Invoice:
        """
        Approves the invoice, moves status to APPROVED (or ISSUED),
        and creates standard General Ledger double-entry posting:
        - Debit: Accounts Receivable (1100-AR-GH)
        - Credit: Revenue (4010-REVENUE-GH or line revenue account)
        - Credit: Tax Payable (2020-TAX-PAYABLE-GH)
        """
        invoice = Invoice.objects.select_related('client', 'category').prefetch_related('lines').get(id=invoice_id)
        if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.PENDING_APPROVAL):
            raise ValidationError(f"Cannot approve invoice with status '{invoice.status}'.")

        invoice.status = InvoiceStatus.ISSUED
        invoice.approved_by = user

        # Perform General Ledger Posting
        ar_account = _get_or_create_account('1100-AR-GH', 'Accounts Receivable (Trade Debtors)', AccountType.ASSET)
        default_rev_account = _get_or_create_account('4010-REVENUE-GH', 'Service & Outsourcing Revenue', AccountType.REVENUE)
        shuttle_rev_account = _get_or_create_account('4020-SHUTTLE-REVENUE-GH', 'Bus Shuttle & Transport Revenue', AccountType.REVENUE)
        tax_payable_account = _get_or_create_account('2020-TAX-PAYABLE-GH', 'Indirect Tax & VAT Payable', AccountType.LIABILITY)

        # Compile lines for GL entry
        gl_lines = [
            {
                'account': ar_account,
                'debit': invoice.total_amount,
                'credit': Decimal('0.0000'),
                'client_id': invoice.client.id,
                'country_code': 'GH',
            }
        ]

        if invoice.subtotal > Decimal('0.0000'):
            # Split revenue by line type: Bus Shuttle lines → 4020-SHUTTLE-REVENUE-GH,
            # all other lines → category income account or 4010-REVENUE-GH.
            shuttle_subtotal = Decimal('0.0000')
            regular_subtotal = Decimal('0.0000')
            for inv_line in invoice.lines.all():
                line_type = (inv_line.custom_fields or {}).get('_line_type', '')
                if line_type == 'BUS_SHUTTLE':
                    shuttle_subtotal += inv_line.line_total
                else:
                    regular_subtotal += inv_line.line_total

            if regular_subtotal > Decimal('0.0000'):
                rev_account = invoice.category.income_account if (invoice.category and invoice.category.income_account) else default_rev_account
                gl_lines.append({
                    'account': rev_account,
                    'debit': Decimal('0.0000'),
                    'credit': regular_subtotal,
                    'client_id': invoice.client.id,
                    'country_code': 'GH',
                })
            if shuttle_subtotal > Decimal('0.0000'):
                gl_lines.append({
                    'account': shuttle_rev_account,
                    'debit': Decimal('0.0000'),
                    'credit': shuttle_subtotal,
                    'client_id': invoice.client.id,
                    'country_code': 'GH',
                })

        if invoice.tax_amount > Decimal('0.0000'):
            gl_lines.append({
                'account': tax_payable_account,
                'debit': Decimal('0.0000'),
                'credit': invoice.tax_amount,
                'client_id': invoice.client.id,
                'country_code': 'GH',
            })

        entry_num = f"JE-INV-{invoice.invoice_number}"
        desc = f"Revenue Recognition for Invoice {invoice.invoice_number} - {invoice.client.name}"

        journal_entry = LedgerService.post_journal_entry(
            entry_number=entry_num,
            posting_date=invoice.issue_date,
            description=desc,
            source_module='INVOICING',
            source_ref=str(invoice.id),
            user=user,
            lines_data=gl_lines
        )
        invoice.journal_entry = journal_entry
        invoice.save()

        # Invalidate Caches across Invoicing, Receivables, and General Ledger
        CacheManager.invalidate_invoicing()
        CacheManager.invalidate_receivables()
        CacheManager.invalidate_ledger()

        return invoice

    @staticmethod
    @transaction.atomic
    def invoice_issue_credit_note(
        *,
        invoice_id: str,
        reason: str,
        credit_amount: Optional[Decimal] = None,
        user=None
    ) -> Invoice:
        """
        Creates an adjusting Credit Note tied to the original invoice.
        Reverses or reduces AR and Revenue accordingly.
        """
        original = Invoice.objects.get(id=invoice_id)
        if original.status in (InvoiceStatus.CANCELLED, InvoiceStatus.VOIDED):
            raise ValidationError(f"Cannot issue credit note for an invoice in '{original.status}' status.")

        amount = Decimal(str(credit_amount)) if credit_amount is not None else original.total_amount
        if amount <= Decimal('0.0000') or amount > original.total_amount:
            raise ValidationError(f"Invalid credit note amount: {amount}. Must be between 0.01 and {original.total_amount}.")

        cn_number = InvoicingService._generate_invoice_number(InvoiceType.CREDIT_NOTE)

        cn = Invoice.objects.create(
            invoice_number=cn_number,
            invoice_type=InvoiceType.CREDIT_NOTE,
            category=original.category,
            description=f"Credit Note for {original.invoice_number}: {reason}",
            client=original.client,
            template=original.template,
            currency=original.currency,
            exchange_rate=original.exchange_rate,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            reference_number=f"CN-REF-{original.invoice_number}",
            status=InvoiceStatus.ISSUED,
            subtotal=amount,
            tax_amount=Decimal('0.0000'),
            total_amount=amount,
            amount_paid=amount,  # Credit notes are self-clearing
            parent_invoice=original,
            created_by=user,
            approved_by=user,
        )

        InvoiceLine.objects.create(
            invoice=cn,
            description=f"Adjustment / Refund: {reason}",
            quantity=Decimal('1.00'),
            unit_of_measurement='Adjustment',
            unit_price=amount,
            line_total=amount,
        )

        # Post Credit Note to GL (Debit Revenue / Sales Returns, Credit AR)
        ar_account = _get_or_create_account('1100-AR-GH', 'Accounts Receivable (Trade Debtors)', AccountType.ASSET)
        rev_return_account = _get_or_create_account('4090-SALES-RETURNS-GH', 'Sales Returns & Allowances', AccountType.REVENUE)

        gl_lines = [
            {
                'account': rev_return_account,
                'debit': amount,
                'credit': Decimal('0.0000'),
                'client_id': original.client.id,
                'country_code': 'GH',
            },
            {
                'account': ar_account,
                'debit': Decimal('0.0000'),
                'credit': amount,
                'client_id': original.client.id,
                'country_code': 'GH',
            }
        ]

        journal_entry = LedgerService.post_journal_entry(
            entry_number=f"JE-CN-{cn.invoice_number}",
            posting_date=timezone.now().date(),
            description=f"Credit Note {cn.invoice_number} against {original.invoice_number}",
            source_module='INVOICING',
            source_ref=str(cn.id),
            user=user,
            lines_data=gl_lines
        )
        cn.journal_entry = journal_entry
        cn.save()

        # Update original invoice amount_paid or status if fully credited
        original.amount_paid += amount
        if original.amount_paid >= original.total_amount:
            original.status = InvoiceStatus.PAID
        original.save()

        # Invalidate Caches
        CacheManager.invalidate_invoicing()
        CacheManager.invalidate_receivables()
        CacheManager.invalidate_ledger()

        return cn

    @staticmethod
    @transaction.atomic
    def invoice_void(*, invoice_id: str, reason: str, user=None) -> Invoice:
        invoice = Invoice.objects.get(id=invoice_id)
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.VOIDED, InvoiceStatus.CANCELLED):
            raise ValidationError(f"Cannot void invoice with status '{invoice.status}'.")

        # Reverse journal entry if one exists
        if invoice.journal_entry:
            LedgerService.reverse_journal_entry(
                entry_id=str(invoice.journal_entry.id),
                user=user,
                reason=f"Voided Invoice {invoice.invoice_number}: {reason}"
            )
            invoice.journal_entry = None

        invoice.status = InvoiceStatus.VOIDED
        invoice.notes = f"{invoice.notes}\n[VOIDED on {timezone.now().date()}]: {reason}".strip()
        invoice.save()

        CacheManager.invalidate_invoicing()
        CacheManager.invalidate_receivables()
        CacheManager.invalidate_ledger()
        return invoice

    # -------------------------------------------------------------------------
    # RECURRING SCHEDULE SERVICES
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def recurring_schedule_create(
        *,
        schedule_name: str,
        client_id: str,
        template_id: Optional[str] = None,
        category_id: Optional[str] = None,
        frequency: str = RecurringFrequency.MONTHLY,
        start_date=None,
        end_date=None,
        auto_issue: bool = False,
        auto_email: bool = False,
        invoice_payload: Dict[str, Any],
    ) -> RecurringSchedule:
        client = Client.objects.get(id=client_id)
        template = InvoiceTemplate.objects.filter(id=template_id).first() if template_id else None
        category = InvoiceCategory.objects.filter(id=category_id).first() if category_id else None
        st_date = start_date or timezone.now().date()

        schedule = RecurringSchedule.objects.create(
            schedule_name=schedule_name.strip(),
            client=client,
            template=template,
            category=category,
            frequency=frequency,
            start_date=st_date,
            end_date=end_date,
            next_run_date=st_date,
            auto_issue=auto_issue,
            auto_email=auto_email,
            invoice_payload=invoice_payload,
            status=RecurringScheduleStatus.ACTIVE
        )
        CacheManager.invalidate_invoicing()
        return schedule

    @staticmethod
    @transaction.atomic
    def recurring_schedule_update(*, schedule_id: str, **fields) -> RecurringSchedule:
        schedule = RecurringSchedule.objects.get(id=schedule_id)
        if 'client_id' in fields:
            cid = fields.pop('client_id')
            schedule.client = Client.objects.get(id=cid)
        if 'template_id' in fields:
            tid = fields.pop('template_id')
            schedule.template = InvoiceTemplate.objects.filter(id=tid).first() if tid else None
        if 'category_id' in fields:
            cat_id = fields.pop('category_id')
            schedule.category = InvoiceCategory.objects.filter(id=cat_id).first() if cat_id else None

        for k, v in fields.items():
            if hasattr(schedule, k):
                setattr(schedule, k, v)

        schedule.save()
        CacheManager.invalidate_invoicing()
        return schedule

    @staticmethod
    @transaction.atomic
    def recurring_schedule_execute_due(as_of_date=None, user=None) -> List[Invoice]:
        """
        Executes active recurring billing schedules whose next_run_date <= as_of_date.
        """
        run_date = as_of_date or timezone.now().date()
        due_schedules = RecurringSchedule.objects.filter(
            status=RecurringScheduleStatus.ACTIVE,
            next_run_date__lte=run_date
        ).select_related('client', 'template', 'category')

        generated_invoices = []
        for schedule in due_schedules:
            payload = schedule.invoice_payload or {}
            lines = payload.get('lines', [])
            if not lines:
                continue

            issue_dt = schedule.next_run_date
            due_dt = issue_dt + datetime.timedelta(days=30)

            inv = InvoicingService.invoice_create(
                client_id=str(schedule.client.id),
                issue_date=issue_dt,
                due_date=due_dt,
                invoice_type=payload.get('invoice_type', InvoiceType.STANDARD),
                category_id=str(schedule.category.id) if schedule.category else None,
                description=payload.get('description', f"Recurring Billing: {schedule.schedule_name}"),
                template_id=str(schedule.template.id) if schedule.template else None,
                currency=payload.get('currency', 'GHS'),
                exchange_rate=Decimal(str(payload.get('exchange_rate', '1.0'))),
                reference_number=payload.get('reference_number', schedule.schedule_name),
                lines=lines,
                custom_fields=payload.get('custom_fields', {}),
                notes=payload.get('notes', ''),
                user=user,
            )

            if schedule.auto_issue:
                inv = InvoicingService.invoice_approve(invoice_id=str(inv.id), user=user)

            generated_invoices.append(inv)

            # Advance next_run_date
            if schedule.frequency == RecurringFrequency.WEEKLY:
                next_date = schedule.next_run_date + datetime.timedelta(days=7)
            elif schedule.frequency == RecurringFrequency.BI_WEEKLY:
                next_date = schedule.next_run_date + datetime.timedelta(days=14)
            elif schedule.frequency == RecurringFrequency.MONTHLY:
                import calendar
                month = schedule.next_run_date.month
                year = schedule.next_run_date.year
                day = schedule.next_run_date.day
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
                max_day = calendar.monthrange(year, month)[1]
                next_date = datetime.date(year, month, min(day, max_day))
            elif schedule.frequency == RecurringFrequency.QUARTERLY:
                next_date = schedule.next_run_date + datetime.timedelta(days=90)
            elif schedule.frequency == RecurringFrequency.ANNUALLY:
                next_date = schedule.next_run_date.replace(year=schedule.next_run_date.year + 1)
            else:
                next_date = schedule.next_run_date + datetime.timedelta(days=30)

            if schedule.end_date and next_date > schedule.end_date:
                schedule.status = RecurringScheduleStatus.COMPLETED
            else:
                schedule.next_run_date = next_date

            schedule.save()

        if generated_invoices:
            CacheManager.invalidate_invoicing()
            CacheManager.invalidate_receivables()

        return generated_invoices
