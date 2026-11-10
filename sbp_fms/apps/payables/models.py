from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class Supplier(BaseModel):
    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=50)
    country_code = models.CharField(max_length=2, default='GH')
    category = models.CharField(max_length=50, blank=True, default='GENERAL')
    registration_number = models.CharField(max_length=50, blank=True, default='')
    contact_person = models.CharField(max_length=100, blank=True, default='')
    telephone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0750'))
    payment_terms_days = models.PositiveSmallIntegerField(default=30)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (TIN: {self.tax_id})"

class PurchaseOrder(BaseModel):
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    total_approved_amount = models.DecimalField(max_digits=18, decimal_places=4)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name}"

class POLine(BaseModel):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    item_code = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField()
    approved_unit_price = models.DecimalField(max_digits=18, decimal_places=4)

class GoodsReceivedNote(BaseModel):
    grn_number = models.CharField(max_length=50, unique=True)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='grns')
    received_date = models.DateField()

class GRNLine(BaseModel):
    grn = models.ForeignKey(GoodsReceivedNote, on_delete=models.CASCADE, related_name='lines')
    item_code = models.CharField(max_length=50)
    received_quantity = models.PositiveIntegerField()

class MatchStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Match'
    MATCHED = 'MATCHED', '3-Way Match Passed (Ready for Payment)'
    BLOCKED_DISCREPANCY = 'BLOCKED_DISCREPANCY', 'Price/Qty Discrepancy Found'
    PAID = 'PAID', 'Settled & Paid'

class SupplierInvoice(BaseModel):
    invoice_number = models.CharField(max_length=50)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='invoices')
    grn = models.ForeignKey(GoodsReceivedNote, on_delete=models.PROTECT, related_name='invoices')
    gross_amount = models.DecimalField(max_digits=18, decimal_places=4)
    wht_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    net_payable_amount = models.DecimalField(max_digits=18, decimal_places=4)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    bill_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    match_status = models.CharField(max_length=30, choices=MatchStatus.choices, default=MatchStatus.PENDING)
    discrepancy_log = models.TextField(blank=True, default='')
    journal_entry = models.ForeignKey('ledger.JournalEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='supplier_invoices')

    class Meta:
        unique_together = ('supplier', 'invoice_number')

    @property
    def balance_due(self) -> Decimal:
        return self.net_payable_amount - self.amount_paid

    def __str__(self):
        return f"Bill {self.invoice_number} from {self.supplier.name} - Status: {self.match_status}"

class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name='lines')
    item_code = models.CharField(max_length=50)
    billed_quantity = models.PositiveIntegerField()
    billed_unit_price = models.DecimalField(max_digits=18, decimal_places=4)

class PayeeType(models.TextChoices):
    SUPPLIER = 'SUPPLIER', 'Supplier'
    EMPLOYEE = 'EMPLOYEE', 'Employee'
    GOVERNMENT = 'GOVERNMENT', 'Government Agency (GRA/SSNIT)'
    CLIENT_DISBURSEMENT = 'CLIENT_DISBURSEMENT', 'Client Disbursement'
    OTHER = 'OTHER', 'Other Payee'

class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
    CHEQUE = 'CHEQUE', 'Cheque'
    MOMO = 'MOMO', 'Mobile Money'
    CASH = 'CASH', 'Cash'

class PaymentVoucherStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted for Review'
    REVIEWED = 'REVIEWED', 'Reviewed'
    APPROVED = 'APPROVED', 'Approved for Payment'
    PAID = 'PAID', 'Paid & Posted'
    REJECTED = 'REJECTED', 'Rejected'
    REVERSED = 'REVERSED', 'Reversed'

class PaymentVoucher(BaseModel):
    voucher_number = models.CharField(max_length=50, unique=True)
    voucher_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    payee_name = models.CharField(max_length=255)
    payee_type = models.CharField(max_length=30, choices=PayeeType.choices, default=PayeeType.SUPPLIER)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name='vouchers')
    supplier_invoice = models.ForeignKey(SupplierInvoice, null=True, blank=True, on_delete=models.SET_NULL, related_name='vouchers')
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    bank_account = models.ForeignKey('treasury.BankAccount', null=True, blank=True, on_delete=models.PROTECT, related_name='vouchers')
    reference_number = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField()
    expense_account = models.ForeignKey('ledger.Account', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    gross_amount = models.DecimalField(max_digits=18, decimal_places=4)
    wht_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    wht_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    other_deductions = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    net_amount = models.DecimalField(max_digits=18, decimal_places=4)
    department = models.CharField(max_length=100, blank=True, default='')
    cost_centre = models.CharField(max_length=100, blank=True, default='')
    client_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PaymentVoucherStatus.choices, default=PaymentVoucherStatus.DRAFT)
    rejection_reason = models.TextField(blank=True, default='')
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    journal_entry = models.ForeignKey('ledger.JournalEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f"Voucher {self.voucher_number} - {self.payee_name} ({self.net_amount}) - Status: {self.status}"

class VoucherLine(BaseModel):
    voucher = models.ForeignKey(PaymentVoucher, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey('ledger.Account', on_delete=models.PROTECT, related_name='+')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=4)

    def __str__(self):
        return f"{self.voucher.voucher_number}: {self.account.code} - {self.amount}"


class ExpenseClaimStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    PAID = 'PAID', 'Settled / Disbursed'


class ExpenseClaimType(models.TextChoices):
    REIMBURSEMENT = 'REIMBURSEMENT', 'Staff Expense Reimbursement'
    CASH_ADVANCE = 'CASH_ADVANCE', 'Staff Cash Advance Request'
    RETIREMENT = 'RETIREMENT', 'Advance Expense Retirement'


class ExpenseClaim(BaseModel):
    claim_number = models.CharField(max_length=50, unique=True, db_index=True)
    claim_date = models.DateField(db_index=True)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='expense_claims')
    claim_type = models.CharField(
        max_length=30,
        choices=ExpenseClaimType.choices,
        default=ExpenseClaimType.REIMBURSEMENT,
        db_index=True
    )
    advance_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    total_expenses = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    net_payable_to_employee = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    status = models.CharField(
        max_length=20,
        choices=ExpenseClaimStatus.choices,
        default=ExpenseClaimStatus.DRAFT,
        db_index=True
    )
    department = models.CharField(max_length=100, blank=True, default='')
    cost_centre = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    settlement_voucher = models.ForeignKey(PaymentVoucher, null=True, blank=True, on_delete=models.SET_NULL, related_name='settled_claims')
    country_code = models.CharField(max_length=2, default='GH')

    class Meta:
        ordering = ['-claim_date', '-created_at']

    def __str__(self):
        return f"{self.claim_number} - {self.employee.email} ({self.total_expenses}) - {self.status}"


class ExpenseClaimLine(BaseModel):
    claim = models.ForeignKey(ExpenseClaim, on_delete=models.CASCADE, related_name='lines')
    expense_date = models.DateField()
    category = models.CharField(max_length=100)
    expense_account = models.ForeignKey('ledger.Account', on_delete=models.PROTECT, related_name='+')
    description = models.TextField()
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    receipt_reference = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['expense_date', 'created_at']

    def __str__(self):
        return f"{self.claim.claim_number}: {self.category} - {self.amount}"


