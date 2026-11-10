from decimal import Decimal
from rest_framework import serializers
from .models import ExchangeRate, FXRevaluationRun, RateType


class ExchangeRateInputSerializer(serializers.Serializer):
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3, default='GHS')
    rate_date = serializers.DateField()
    rate = serializers.DecimalField(max_digits=18, decimal_places=6)
    rate_type = serializers.ChoiceField(choices=RateType.choices, default=RateType.CLOSING)


class ExchangeRateOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ['id', 'from_currency', 'to_currency', 'rate_date', 'rate', 'rate_type', 'created_at']


class LiveExchangeRateQuerySerializer(serializers.Serializer):
    from_currency = serializers.CharField(max_length=3, default='USD', help_text="Base currency to convert from (e.g. USD, EUR, GBP)")
    to_currency = serializers.CharField(max_length=3, default='GHS', help_text="Target currency to convert into (e.g. GHS, NGN, KES)")
    force_refresh = serializers.BooleanField(default=False, required=False, help_text="Bypass short-lived cache and query Groq AI directly")


class LiveExchangeRateOutputSerializer(serializers.Serializer):
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    rate = serializers.DecimalField(max_digits=18, decimal_places=6)
    source = serializers.CharField(help_text="Exchange source, e.g. xe.com / Groq AI")
    is_cached = serializers.BooleanField(help_text="True if served from fast memory cache, False if freshly queried online")
    timestamp = serializers.CharField()


class FXRevaluationRunInputSerializer(serializers.Serializer):
    revaluation_date = serializers.DateField()
    reporting_currency = serializers.CharField(max_length=3, default='GHS')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class FXRevaluationRunOutputSerializer(serializers.ModelSerializer):
    journal_entry_number = serializers.CharField(source='journal_entry.entry_number', read_only=True, default=None)

    class Meta:
        model = FXRevaluationRun
        fields = [
            'id', 'revaluation_date', 'reporting_currency', 'total_gain_loss',
            'journal_entry', 'journal_entry_number', 'notes', 'created_at'
        ]


class ConsolidatedTrialBalanceItemSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    account_type = serializers.CharField()
    original_currency = serializers.CharField()
    original_debit = serializers.DecimalField(max_digits=18, decimal_places=4)
    original_credit = serializers.DecimalField(max_digits=18, decimal_places=4)
    exchange_rate = serializers.DecimalField(max_digits=18, decimal_places=6)
    consolidated_debit = serializers.DecimalField(max_digits=18, decimal_places=4)
    consolidated_credit = serializers.DecimalField(max_digits=18, decimal_places=4)


class ConsolidatedTrialBalanceOutputSerializer(serializers.Serializer):
    as_of_date = serializers.CharField()
    reporting_currency = serializers.CharField()
    accounts = ConsolidatedTrialBalanceItemSerializer(many=True)
    total_debit = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_credit = serializers.DecimalField(max_digits=18, decimal_places=4)
    imbalance = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_balanced = serializers.BooleanField()
