from rest_framework import serializers
from .models import TaxRule

class TaxRuleOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = '__all__'

class TaxCalculationInputSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2, default='GH')
    gross_salary = serializers.DecimalField(max_digits=18, decimal_places=4)
