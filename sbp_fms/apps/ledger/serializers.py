from rest_framework import serializers
from .models import Account, JournalEntry, JournalLine

class AccountOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'code', 'name', 'account_type', 'currency', 'country_code', 'is_active', 'description', 'created_at']

class AccountCreateInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=255)
    account_type = serializers.CharField(max_length=20)
    currency = serializers.CharField(max_length=3, default='GHS')
    country_code = serializers.CharField(max_length=2, default='GH')
    description = serializers.CharField(required=False, allow_blank=True, default='')

class JournalLineOutputSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalLine
        fields = ['id', 'account', 'account_code', 'account_name', 'debit', 'credit', 'client_id', 'cost_centre', 'country_code']

class JournalEntryOutputSerializer(serializers.ModelSerializer):
    lines = JournalLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = ['id', 'entry_number', 'posting_date', 'status', 'description', 'source_module', 'source_reference_id', 'created_by', 'approved_by', 'lines', 'created_at']

class JournalLineInputSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    debit = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    credit = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    cost_centre = serializers.CharField(required=False, allow_blank=True)
    country_code = serializers.CharField(max_length=2, default='GH')

class JournalEntryCreateInputSerializer(serializers.Serializer):
    entry_number = serializers.CharField(max_length=50)
    posting_date = serializers.DateField()
    description = serializers.CharField()
    source_module = serializers.CharField(max_length=50)
    source_reference_id = serializers.CharField(max_length=100)
    lines = JournalLineInputSerializer(many=True)

class JournalEntryReverseInputSerializer(serializers.Serializer):
    reason = serializers.CharField()
