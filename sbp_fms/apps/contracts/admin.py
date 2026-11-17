from django.contrib import admin
from apps.contracts.models import Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'title', 'client', 'start_date', 'end_date', 'total_contract_value', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('contract_number', 'title', 'client__name')
