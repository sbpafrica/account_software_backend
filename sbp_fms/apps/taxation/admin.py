from django.contrib import admin
from apps.taxation.models import TaxRule


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ('tax_type', 'country_code', 'rate', 'bracket_min', 'bracket_max', 'effective_from', 'created_at')
    list_filter = ('tax_type', 'country_code')
    search_fields = ('tax_type', 'country_code')
