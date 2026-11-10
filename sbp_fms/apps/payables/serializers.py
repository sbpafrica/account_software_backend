from rest_framework import serializers
from .models import (
    Supplier, PurchaseOrder, POLine,
    GoodsReceivedNote, GRNLine,
    SupplierInvoice, InvoiceLine
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
