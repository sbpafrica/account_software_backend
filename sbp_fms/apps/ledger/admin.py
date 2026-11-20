from django.contrib import admin
from apps.ledger.models import CompanyProfile, Department, CostCentre, Account, JournalEntry, JournalLine


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 1
    fields = ('account', 'debit', 'credit', 'country_code')


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'country_code', 'tax_identification_number', 'base_currency', 'created_at')
    search_fields = ('company_name', 'tax_identification_number')
    list_filter = ('country_code', 'base_currency')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(organization__memberships__user=request.user).distinct()
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == "organization":
            from apps.organizations.models import Organization
            kwargs["queryset"] = Organization.objects.filter(
                memberships__user=request.user,
                memberships__role__in=['OWNER', 'ADMIN']
            ).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)


@admin.register(CostCentre)
class CostCentreAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'currency', 'country_code', 'is_active')
    list_filter = ('account_type', 'country_code', 'currency', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_number', 'posting_date', 'status', 'source_module', 'created_by', 'created_at')
    list_filter = ('status', 'source_module')
    search_fields = ('entry_number', 'description')
    inlines = [JournalLineInline]
    readonly_fields = ('created_at',)
