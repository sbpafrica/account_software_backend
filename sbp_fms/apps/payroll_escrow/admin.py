from django.contrib import admin
from apps.payroll_escrow.models import PayrollBatch


@admin.register(PayrollBatch)
class PayrollBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_code', 'client_name', 'country_code', 'month', 'year', 'total_net_salaries', 'status', 'created_at')
    list_filter = ('status', 'country_code', 'year')
    search_fields = ('batch_code', 'client_name')
