from decimal import Decimal
from django.db import models
from apps.common.models import BaseModel

class Supplier(BaseModel):
    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=50)
    country_code = models.CharField(max_length=2, default='GH')
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0750'))
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)

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
    match_status = models.CharField(max_length=30, choices=MatchStatus.choices, default=MatchStatus.PENDING)
    discrepancy_log = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('supplier', 'invoice_number')

    def __str__(self):
        return f"Bill {self.invoice_number} from {self.supplier.name} - Status: {self.match_status}"

class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name='lines')
    item_code = models.CharField(max_length=50)
    billed_quantity = models.PositiveIntegerField()
    billed_unit_price = models.DecimalField(max_digits=18, decimal_places=4)
