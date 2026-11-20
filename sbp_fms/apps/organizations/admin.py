from django.contrib import admin
from apps.organizations.models import (
    Organization,
    SubscriptionPlan,
    SubscriptionTransaction,
    PaymentWebhookLog,
    OrganizationMembership,
    OrganizationInvitation
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'plan', 'base_currency', 'is_inhouse', 'is_active', 'plan_expires_at', 'created_at')
    list_filter = ('plan', 'is_inhouse', 'is_active', 'base_currency')
    search_fields = ('name', 'slug', 'billing_email')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(memberships__user=request.user).distinct()
        return qs

    def has_add_permission(self, request):
        # Platform-level multi-tenancy: Only platform superadmins can create organizations
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        # Only platform superadmins can permanently delete organizations
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return OrganizationMembership.objects.filter(
                user=request.user,
                role__in=['OWNER', 'ADMIN']
            ).exists()
        return obj.memberships.filter(
            user=request.user,
            role__in=['OWNER', 'ADMIN']
        ).exists()


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'price', 'currency', 'interval', 'is_active', 'is_public', 'trial_period_days')
    list_filter = ('currency', 'interval', 'is_active', 'is_public')
    search_fields = ('name', 'code')
    prepopulated_fields = {'code': ('name',)}

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SubscriptionTransaction)
class SubscriptionTransactionAdmin(admin.ModelAdmin):
    list_display = ('organization', 'plan', 'amount', 'currency', 'status', 'reference', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('organization__name', 'reference')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(organization__memberships__user=request.user).distinct()
        return qs

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ('organization', 'user', 'role', 'is_default', 'created_at')
    list_filter = ('role', 'is_default')
    search_fields = ('organization__name', 'user__email')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(organization__memberships__user=request.user).distinct()
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            if db_field.name == "organization":
                kwargs["queryset"] = Organization.objects.filter(
                    memberships__user=request.user,
                    memberships__role__in=['OWNER', 'ADMIN']
                ).distinct()
            elif db_field.name == "user":
                from apps.users.models import User
                kwargs["queryset"] = User.objects.filter(
                    organization_memberships__organization__memberships__user=request.user
                ).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ('organization', 'email', 'role', 'accepted', 'created_at')
    list_filter = ('role', 'accepted')
    search_fields = ('organization__name', 'email')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(organization__memberships__user=request.user).distinct()
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == "organization":
            kwargs["queryset"] = Organization.objects.filter(
                memberships__user=request.user,
                memberships__role__in=['OWNER', 'ADMIN']
            ).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'provider', 'reference', 'processed', 'created_at')
    list_filter = ('provider', 'processed', 'event_type')
    search_fields = ('reference', 'event_type')

    def has_module_permission(self, request):
        # Platform-level payment gateway webhooks are restricted to platform superadmins
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
