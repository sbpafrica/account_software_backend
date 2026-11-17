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


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'price', 'currency', 'interval', 'is_active', 'is_public', 'trial_period_days')
    list_filter = ('currency', 'interval', 'is_active', 'is_public')
    search_fields = ('name', 'code')
    prepopulated_fields = {'code': ('name',)}


@admin.register(SubscriptionTransaction)
class SubscriptionTransactionAdmin(admin.ModelAdmin):
    list_display = ('organization', 'plan', 'amount', 'currency', 'status', 'reference', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('organization__name', 'reference')


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ('organization', 'user', 'role', 'is_default', 'created_at')
    list_filter = ('role', 'is_default')
    search_fields = ('organization__name', 'user__email')


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ('organization', 'email', 'role', 'accepted', 'created_at')
    list_filter = ('role', 'accepted')
    search_fields = ('organization__name', 'email')


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'provider', 'reference', 'processed', 'created_at')
    list_filter = ('provider', 'processed', 'event_type')
    search_fields = ('reference', 'event_type')
