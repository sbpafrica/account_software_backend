from rest_framework import serializers
from .models import BankAccount, BankTransaction

class BankAccountOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = '__all__'

class BankTransactionOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransaction
        fields = '__all__'
