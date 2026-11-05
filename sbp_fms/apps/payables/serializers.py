from rest_framework import serializers
from .models import Supplier, SupplierInvoice, InvoiceLine

class SupplierOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

class InvoiceLineOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = '__all__'

class SupplierInvoiceOutputSerializer(serializers.ModelSerializer):
    lines = InvoiceLineOutputSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = '__all__'
