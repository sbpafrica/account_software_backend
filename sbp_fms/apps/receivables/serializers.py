from rest_framework import serializers
from .models import Client, ClientInvoice

class ClientOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

class ClientInvoiceOutputSerializer(serializers.ModelSerializer):
    balance_due = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = ClientInvoice
        fields = '__all__'
