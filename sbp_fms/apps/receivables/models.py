from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class Client(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    country_code = models.CharField(max_length=2, default='GH')
    category = models.CharField(max_length=50, blank=True, default='CORPORATE')
    tax_id = models.CharField(max_length=50, blank=True, default='')
    registration_number = models.CharField(max_length=50, blank=True, default='')
    contact_person = models.CharField(max_length=100, blank=True, default='')
    telephone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    billing_address = models.TextField(blank=True, default='')
    credit_limit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('50000.0000'))
    payment_terms_days = models.PositiveSmallIntegerField(default=30)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    default_template = models.ForeignKey('ClientInvoiceTemplate', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class InvoiceLayoutStyle(models.TextChoices):
    MODERN = 'MODERN', 'Modern Clean'
    CLASSIC = 'CLASSIC', 'Classic Standard'
    CORPORATE = 'CORPORATE', 'Corporate Professional'
    MINIMAL = 'MINIMAL', 'Minimalist'
    DETAILED_STAFFING = 'DETAILED_STAFFING', 'Detailed Staffing & Timesheet'


class ClientInvoiceTemplate(BaseModel):
    template_name = models.CharField(max_length=100)
    preset_code = models.CharField(max_length=50, blank=True, default='')
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.CASCADE, related_name='invoice_templates')
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
        help_text="Header-level custom fields: list of dicts with key, label, type, required, default_value, placeholder, options"
    )
    line_custom_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="Table line-item custom columns: list of dicts with key, label, type, required, default_value, placeholder, options"
    )
    custom_field_definitions = models.JSONField(
        default=list,
        blank=True,
        help_text="Legacy alias for header_custom_fields"
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.header_custom_fields and self.custom_field_definitions:
            self.header_custom_fields = self.custom_field_definitions
        elif not self.custom_field_definitions and self.header_custom_fields:
            self.custom_field_definitions = self.header_custom_fields
        super().save(*args, **kwargs)

    def __str__(self):
        owner = self.client.name if self.client else "Global Default"
        return f"{self.template_name} ({owner}) - {self.layout_style}"


class ClientInvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    ISSUED = 'ISSUED', 'Issued to Client'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Fully Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'
    VOIDED = 'VOIDED', 'Voided'

class ClientInvoice(BaseModel):
    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='invoices')
    template = models.ForeignKey(ClientInvoiceTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    issue_date = models.DateField()
    due_date = models.DateField(db_index=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    discount_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(max_length=20, choices=ClientInvoiceStatus.choices, default=ClientInvoiceStatus.DRAFT)
    notes = models.TextField(blank=True, default='')
    terms_and_conditions = models.TextField(blank=True, default='')
    custom_fields = models.JSONField(default=dict, blank=True, help_text="Custom client-specific key-value values (e.g. po_number, cost_center, site_location)")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    journal_entry = models.ForeignKey('ledger.JournalEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='client_invoices')

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.client.name}) - Balance: {self.balance_due}"

class ClientInvoiceLine(BaseModel):
    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit_of_measurement = models.CharField(max_length=20, default='Unit')
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tax_code = models.CharField(max_length=20, default='EXEMPT')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    line_total = models.DecimalField(max_digits=18, decimal_places=4)
    custom_fields = models.JSONField(default=dict, blank=True, help_text="Line-level custom field values (e.g. employee_name, timesheet_code, department)")

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description} ({self.line_total})"

class PaymentReceiptStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    REVERSED = 'REVERSED', 'Reversed'

class PaymentReceipt(BaseModel):
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='receipts')
    amount_received = models.DecimalField(max_digits=18, decimal_places=4)
    payment_method = models.CharField(max_length=30, default='BANK_TRANSFER')
    bank_account = models.ForeignKey('treasury.BankAccount', on_delete=models.PROTECT, related_name='receipts')
    reference_number = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    unallocated_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(max_length=20, choices=PaymentReceiptStatus.choices, default=PaymentReceiptStatus.CONFIRMED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    journal_entry = models.ForeignKey('ledger.JournalEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f"Receipt {self.receipt_number} from {self.client.name} - {self.amount_received}"

class ReceiptAllocation(BaseModel):
    receipt = models.ForeignKey(PaymentReceipt, on_delete=models.CASCADE, related_name='allocations')
    invoice = models.ForeignKey(ClientInvoice, on_delete=models.PROTECT, related_name='allocations')
    amount_allocated = models.DecimalField(max_digits=18, decimal_places=4)

    def __str__(self):
        return f"Allocation: {self.amount_allocated} of Receipt {self.receipt.receipt_number} to {self.invoice.invoice_number}"

