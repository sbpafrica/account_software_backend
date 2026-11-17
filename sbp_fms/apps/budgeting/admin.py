from django.contrib import admin
from apps.budgeting.models import Budget, BudgetLine


class BudgetLineInline(admin.TabularInline):
    model = BudgetLine
    extra = 1


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'financial_year', 'department', 'cost_centre', 'status', 'total_budget', 'created_at')
    list_filter = ('status', 'financial_year')
    search_fields = ('name',)
    inlines = [BudgetLineInline]
