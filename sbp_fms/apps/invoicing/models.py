from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel


class InvoiceCategory(BaseModel):
    """
    Dynamic, Admin-managed business vertical category for invoices and billable items.
    Allows admins to add new business categories on the fly (e.g. Workforce Outsourcing,
    Payroll Administration, Haulage & Fleet, Expatriate Visa Services, Catering).
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    income_account = models.ForeignKey('ledger.Account', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        verbose_name = 'Invoice Category'
        verbose_name_plural = 'Invoice Categories'
        ordering = ['name']


class InvoiceType(models.TextChoices):
    STANDARD = 'STANDARD', 'Standard Commercial / Tax Invoice'
    PROFORMA = 'PROFORMA', 'Pro-forma Invoice / Estimate'
    CREDIT_NOTE = 'CREDIT_NOTE', 'Credit Note (Adjustment / Refund)'
    DEBIT_NOTE = 'DEBIT_NOTE', 'Debit Note (Supplemental Charge)'


class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    ISSUED = 'ISSUED', 'Issued to Client'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Fully Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'
    VOIDED = 'VOIDED', 'Voided'


class InvoiceLayoutStyle(models.TextChoices):
    MODERN = 'MODERN', 'Modern Clean'
    CLASSIC = 'CLASSIC', 'Classic Standard'
    CORPORATE = 'CORPORATE', 'Corporate Professional'
    MINIMAL = 'MINIMAL', 'Minimalist'
    DETAILED_STAFFING = 'DETAILED_STAFFING', 'Detailed Staffing & Timesheet'


class InvoiceTemplate(BaseModel):
    """
    Invoice Builder Template definition.
    Configures branding colors, layout styles, toggles, and dynamic header/line fields.
    Can be assigned globally or customized per client.
    """
    template_name = models.CharField(max_length=100)
    preset_code = models.CharField(max_length=50, blank=True, default='')
    client = models.ForeignKey('receivables.Client', null=True, blank=True, on_delete=models.CASCADE, related_name='invoicing_templates')
    layout_style = models.CharField(max_length=30, choices=InvoiceLayoutStyle.choices, default=InvoiceLayoutStyle.MODERN)
    primary_color = models.CharField(max_length=20, default='#102a43')
    secondary_color = models.CharField(max_length=20, default='#243b53')
    accent_color = models.CharField(max_length=20, default='#0ea5e9')
    logo_url = models.URLField(max_length=500, blank=True, default='')
    show_logo = models.BooleanField(default=True)
    font_family = models.CharField(max_length=100, default='Inter, sans-serif')
    invoice_title = models.CharField(max_length=100, default='TAX INVOICE')
    show_tax_breakdown = models.BooleanField(default=True)
    show_bank_details = models.BooleanField(default=True)
    show_due_date_badge = models.BooleanField(default=True)
    show_discount = models.BooleanField(default=True)
    show_unit_of_measure = models.BooleanField(default=True)
    default_notes = models.TextField(blank=True, default='Thank you for partnering with SBP Africa Group.')
    default_terms = models.TextField(blank=True, default='Payment is due within payment terms. All bank charges borne by payer.')
    footer_text = models.CharField(max_length=255, blank=True, default='SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg')
    header_custom_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="Header custom fields definitions: list of {key, label, type, required, default_value, placeholder, options}"
    )
    line_custom_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="Line custom table column definitions: list of {key, label, type, required, default_value, placeholder, options}"
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        owner = self.client.name if self.client else "Global Default"
        return f"{self.template_name} ({owner}) - {self.layout_style}"

    class Meta:
        ordering = ['-is_default', 'template_name']


class BillableItem(BaseModel):
    """
    Catalog of billable services, workforce rates, and placement fees.
    """
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(InvoiceCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='items')
    description = models.TextField(blank=True, default='')
    default_unit = models.CharField(max_length=50, default='Unit', help_text="e.g. Days, Hours, Month, Headcount, Project")
    default_unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    default_tax_code = models.CharField(max_length=50, default='VAT_STANDARD')
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.1500'))
    income_account = models.ForeignKey('ledger.Account', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.default_unit_price} GHS)"

    class Meta:
        ordering = ['code']


class Invoice(BaseModel):
    """
    Comprehensive Commercial & Tax Invoice.
    Supports Standard, Pro-forma, Credit Note, and Debit Note types with multi-currency,
    dynamic custom fields, and General Ledger posting integration.
    """
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=30, choices=InvoiceType.choices, default=InvoiceType.STANDARD)
    category = models.ForeignKey(InvoiceCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    description = models.TextField(blank=True, default='', help_text="High-level narrative or summary of the bill")
    client = models.ForeignKey('receivables.Client', on_delete=models.PROTECT, related_name='invoicing_invoices')
    template = models.ForeignKey(InvoiceTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    currency = models.CharField(max_length=3, default='GHS')
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal('1.000000'))
    issue_date = models.DateField()
    due_date = models.DateField(db_index=True)
    billing_period_start = models.DateField(null=True, blank=True)
    billing_period_end = models.DateField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True, default='', help_text="Client PO number or contract reference")
    status = models.CharField(max_length=30, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    discount_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    total_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    amount_paid = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    custom_fields = models.JSONField(default=dict, blank=True, help_text="Header custom field key-values (e.g. po_number, site_location)")
    notes = models.TextField(blank=True, default='')
    terms_and_conditions = models.TextField(blank=True, default='')
    footer_text = models.CharField(max_length=255, blank=True, default='')
    journal_entry = models.ForeignKey('ledger.JournalEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    parent_invoice = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_invoices', help_text="Original invoice referenced by this Credit Note or Debit Note")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    @property
    def is_paid(self) -> bool:
        return self.status == InvoiceStatus.PAID or (self.amount_paid >= self.total_amount and self.total_amount > Decimal('0.0000'))

    def __str__(self):
        cat_str = f" [{self.category.code}]" if self.category else ""
        return f"{self.invoice_number}{cat_str} - {self.client.name} ({self.total_amount} {self.currency})"

    class Meta:
        ordering = ['-issue_date', '-created_at']


class InvoiceLine(BaseModel):
    """
    Granular invoice line item with support for catalog items, free-form service lines,
    tax calculation, and custom column values (staff name, role, days worked, department).
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(BillableItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoice_lines')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit_of_measurement = models.CharField(max_length=50, default='Unit')
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tax_code = models.CharField(max_length=50, default='EXEMPT')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    line_total = models.DecimalField(max_digits=18, decimal_places=4)
    custom_fields = models.JSONField(default=dict, blank=True, help_text="Line custom column key-values (e.g. staff_name, role_designation, days_worked)")
    revenue_account = models.ForeignKey('ledger.Account', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description} ({self.line_total})"


class InvoiceTaxLine(BaseModel):
    """
    Statutory tax breakdown (NHIL 2.5%, GETFund 2.5%, COVID 1.0%, VAT 15.0%, WHT).
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='tax_lines')
    tax_type = models.CharField(max_length=50)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    base_amount = models.DecimalField(max_digits=18, decimal_places=4)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.tax_type} ({self.tax_amount})"


class RecurringFrequency(models.TextChoices):
    WEEKLY = 'WEEKLY', 'Weekly'
    BI_WEEKLY = 'BI_WEEKLY', 'Bi-Weekly'
    MONTHLY = 'MONTHLY', 'Monthly'
    QUARTERLY = 'QUARTERLY', 'Quarterly'
    ANNUALLY = 'ANNUALLY', 'Annually'


class RecurringScheduleStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    COMPLETED = 'COMPLETED', 'Completed'


class RecurringSchedule(BaseModel):
    """
    Recurring invoice profile for monthly outsourced staffing and payroll contracts.
    """
    schedule_name = models.CharField(max_length=100)
    client = models.ForeignKey('receivables.Client', on_delete=models.PROTECT, related_name='invoicing_schedules')
    template = models.ForeignKey(InvoiceTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    category = models.ForeignKey(InvoiceCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    frequency = models.CharField(max_length=20, choices=RecurringFrequency.choices, default=RecurringFrequency.MONTHLY)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_run_date = models.DateField(db_index=True)
    auto_issue = models.BooleanField(default=False)
    auto_email = models.BooleanField(default=False)
    invoice_payload = models.JSONField(default=dict, help_text="Template invoice payload: lines, custom fields, notes")
    status = models.CharField(max_length=20, choices=RecurringScheduleStatus.choices, default=RecurringScheduleStatus.ACTIVE)

    def __str__(self):
        return f"{self.schedule_name} - {self.client.name} ({self.frequency})"


class InvoiceDeliveryLog(BaseModel):
    """
    Delivery and dispatch audit log for sent invoices (Email, Portal, WhatsApp).
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='delivery_logs')
    delivery_channel = models.CharField(max_length=50, default='EMAIL')
    recipient_email = models.CharField(max_length=255, blank=True, default='')
    sent_at = models.DateTimeField(auto_now_add=True)
    is_success = models.BooleanField(default=True)
    failure_reason = models.TextField(blank=True, default='')

    def __str__(self):
        status_str = "SUCCESS" if self.is_success else "FAILED"
        return f"{self.invoice.invoice_number} via {self.delivery_channel} to {self.recipient_email} - {status_str}"
