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
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

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
    issue_date = models.DateField()
    due_date = models.DateField(db_index=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    discount_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(max_length=20, choices=ClientInvoiceStatus.choices, default=ClientInvoiceStatus.DRAFT)
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

