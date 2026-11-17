from django.contrib import admin
from apps.consolidation.models import ExchangeRate, FXRevaluationRun


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('from_currency', 'to_currency', 'rate_date', 'rate', 'rate_type', 'created_at')
    list_filter = ('from_currency', 'to_currency', 'rate_type')
    search_fields = ('from_currency', 'to_currency')


@admin.register(FXRevaluationRun)
class FXRevaluationRunAdmin(admin.ModelAdmin):
    list_display = ('revaluation_date', 'reporting_currency', 'total_gain_loss', 'created_by', 'created_at')
    list_filter = ('reporting_currency',)
