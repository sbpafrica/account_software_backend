from decimal import Decimal
from rest_framework import serializers
from .models import (
    Supplier, PurchaseOrder, POLine,
    GoodsReceivedNote, GRNLine,
    SupplierInvoice, InvoiceLine,
    PaymentVoucher, VoucherLine,
    ExpenseClaim, ExpenseClaimLine
)


# ============================================================================
# 1. SUPPLIERS
# ============================================================================

class SupplierOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class SupplierCreateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    tax_id = serializers.CharField(max_length=50)
    country_code = serializers.CharField(max_length=2, default='GH')
    wht_rate = serializers.DecimalField(max_digits=5, decimal_places=4, default=0.0750)
    bank_account_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')


class SupplierUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    tax_id = serializers.CharField(max_length=50, required=False)
    country_code = serializers.CharField(max_length=2, required=False)
    wht_rate = serializers.DecimalField(max_digits=5, decimal_places=4, required=False)
    bank_account_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


# ============================================================================
# 2. PURCHASE ORDERS
# ============================================================================

class POLineOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = POLine
        fields = '__all__'


class POLineInputSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=50)
    quantity = serializers.IntegerField(min_value=1)
    approved_unit_price = serializers.DecimalField(max_digits=18, decimal_places=4)


class PurchaseOrderOutputSerializer(serializers.ModelSerializer):
    lines = POLineOutputSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'


class PurchaseOrderCreateInputSerializer(serializers.Serializer):
    po_number = serializers.CharField(max_length=50)
    supplier_id = serializers.UUIDField()
    total_approved_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    lines = POLineInputSerializer(many=True, required=False, default=list)


class PurchaseOrderUpdateInputSerializer(serializers.Serializer):
    total_approved_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    is_approved = serializers.BooleanField(required=False)


# ============================================================================
# 3. GOODS RECEIVED NOTES
# ============================================================================

class GRNLineOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRNLine
        fields = '__all__'


class GRNLineInputSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=50)
    received_quantity = serializers.IntegerField(min_value=1)


class GoodsReceivedNoteOutputSerializer(serializers.ModelSerializer):
    lines = GRNLineOutputSerializer(many=True, read_only=True)
    po_number = serializers.CharField(source='po.po_number', read_only=True)

    class Meta:
        model = GoodsReceivedNote
        fields = '__all__'


class GoodsReceivedNoteCreateInputSerializer(serializers.Serializer):
    grn_number = serializers.CharField(max_length=50)
    po_id = serializers.UUIDField()
    received_date = serializers.DateField()
    lines = GRNLineInputSerializer(many=True, required=False, default=list)


class GoodsReceivedNoteUpdateInputSerializer(serializers.Serializer):
    received_date = serializers.DateField(required=False)


# ============================================================================
# 4. SUPPLIER INVOICES & 3-WAY MATCH
# ============================================================================

class InvoiceLineOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = '__all__'


class InvoiceLineInputSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=50)
    billed_quantity = serializers.IntegerField(min_value=1)
    billed_unit_price = serializers.DecimalField(max_digits=18, decimal_places=4)


class SupplierInvoiceOutputSerializer(serializers.ModelSerializer):
    lines = InvoiceLineOutputSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = '__all__'


class SupplierInvoiceCreateInputSerializer(serializers.Serializer):
    invoice_number = serializers.CharField(max_length=50)
    supplier_id = serializers.UUIDField()
    po_id = serializers.UUIDField()
    grn_id = serializers.UUIDField()
    gross_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    lines = InvoiceLineInputSerializer(many=True, required=False, default=list)


class SupplierInvoiceUpdateInputSerializer(serializers.Serializer):
    gross_amount = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    match_status = serializers.CharField(max_length=30, required=False)


class ThreeWayMatchOutputSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()


class SupplierInvoicePublicStatusOutputSerializer(serializers.Serializer):
    invoice_number = serializers.CharField()
    match_status = serializers.CharField()
    net_payable_amount = serializers.DecimalField(max_digits=18, decimal_places=4)


# ============================================================================
# 5. PAYMENT VOUCHERS
# ============================================================================

from .models import PaymentVoucher, VoucherLine


class VoucherLineOutputSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = VoucherLine
        fields = '__all__'


class VoucherLineInputSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    description = serializers.CharField(max_length=255, required=False, default='')
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)


class PaymentVoucherOutputSerializer(serializers.ModelSerializer):
    lines = VoucherLineOutputSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    prepared_by_email = serializers.CharField(source='prepared_by.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)

    class Meta:
        model = PaymentVoucher
        fields = '__all__'


class PaymentVoucherCreateInputSerializer(serializers.Serializer):
    voucher_number = serializers.CharField(max_length=50)
    voucher_date = serializers.DateField()
    payee_name = serializers.CharField(max_length=255)
    payee_type = serializers.CharField(max_length=30, required=False, default='SUPPLIER')
    supplier_id = serializers.UUIDField(required=False, allow_null=True)
    supplier_invoice_id = serializers.UUIDField(required=False, allow_null=True)
    payment_method = serializers.CharField(max_length=30, required=False, default='BANK_TRANSFER')
    bank_account_id = serializers.UUIDField(required=False, allow_null=True)
    gross_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    wht_rate = serializers.DecimalField(max_digits=5, decimal_places=4, required=False, default=Decimal('0.0000'))
    other_deductions = serializers.DecimalField(max_digits=18, decimal_places=4, required=False, default=Decimal('0.0000'))
    description = serializers.CharField(required=False, allow_blank=True, default='')
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    cost_centre = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    client_id = serializers.UUIDField(required=False, allow_null=True)
    lines = VoucherLineInputSerializer(many=True, required=False, default=list)


class PaymentVoucherMarkPaidInputSerializer(serializers.Serializer):
    payment_date = serializers.DateField(required=False, allow_null=True)
    bank_account_id = serializers.UUIDField(required=False, allow_null=True)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')


class PaymentVoucherRejectInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class ExpenseClaimLineOutputSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='expense_account.code', read_only=True)
    account_name = serializers.CharField(source='expense_account.name', read_only=True)

    class Meta:
        model = ExpenseClaimLine
        fields = '__all__'


class ExpenseClaimOutputSerializer(serializers.ModelSerializer):
    employee_email = serializers.EmailField(source='employee.email', read_only=True)
    employee_name = serializers.SerializerMethodField()
    approved_by_email = serializers.EmailField(source='approved_by.email', read_only=True)
    lines = ExpenseClaimLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = ExpenseClaim
        fields = '__all__'

    def get_employee_name(self, obj) -> str:
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip() or obj.employee.email


class ExpenseClaimLineInputSerializer(serializers.Serializer):
    expense_date = serializers.DateField(required=False)
    category = serializers.CharField(max_length=100)
    expense_account_id = serializers.UUIDField()
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    receipt_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')


class ExpenseClaimCreateInputSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    claim_date = serializers.DateField()
    claim_type = serializers.CharField(max_length=30, default='REIMBURSEMENT', required=False)
    advance_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'), required=False)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    cost_centre = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    country_code = serializers.CharField(max_length=2, default='GH', required=False)
    lines = ExpenseClaimLineInputSerializer(many=True, required=False, default=list)


class ExpenseClaimSettleInputSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField(required=False, allow_null=True)


class ExpenseClaimRejectInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, default='Rejected', required=False)


class APAgingReportOutputSerializer(serializers.Serializer):
    country_code = serializers.CharField()
    current_0_30_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    overdue_31_60_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    overdue_61_90_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    overdue_90_plus_days = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_payables = serializers.DecimalField(max_digits=18, decimal_places=4)


class SupplierStatementTransactionSerializer(serializers.Serializer):
    date = serializers.CharField()
    reference = serializers.CharField()
    type = serializers.CharField()
    billed = serializers.DecimalField(max_digits=18, decimal_places=4)
    paid = serializers.DecimalField(max_digits=18, decimal_places=4)
    balance = serializers.DecimalField(max_digits=18, decimal_places=4)


class SupplierStatementOutputSerializer(serializers.Serializer):
    supplier_id = serializers.CharField()
    supplier_name = serializers.CharField()
    supplier_code = serializers.CharField()
    country_code = serializers.CharField()
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    transactions = SupplierStatementTransactionSerializer(many=True)


