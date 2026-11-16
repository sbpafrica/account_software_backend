from django.urls import path
from .views import (
    OrganizationRegisterPublicApi,
    OrganizationMeListApi,
    OrganizationSwitchApi,
    OrganizationInviteApi,
    OrganizationAcceptInviteApi,
    OrganizationDetailApi,
    OrganizationDeactivateApi,
    OrganizationReactivateApi,
    OrganizationAdminListApi,
    SubscriptionPlanListPublicApi,
    SubscriptionPlanListCreateAdminApi,
    SubscriptionPlanDetailAdminApi,
    BillingInitializeApi,
    BillingVerifyApi,
    BillingTransactionsListApi,
    PaystackWebhookPublicApi,
)

urlpatterns = [
    # Public self-service SaaS onboarding (Registration with 30-Day Free Trial)
    path('register/', OrganizationRegisterPublicApi.as_view(), name='organization-register-public'),

    # Superadmin Platform Organization Management
    path('admin/list/', OrganizationAdminListApi.as_view(), name='organization-admin-list'),

    # User's tenant memberships & tenant switcher
    path('me/', OrganizationMeListApi.as_view(), name='organization-me-list'),
    path('switch/', OrganizationSwitchApi.as_view(), name='organization-switch'),

    # Team invitations
    path('invite/', OrganizationInviteApi.as_view(), name='organization-invite'),
    path('accept-invite/', OrganizationAcceptInviteApi.as_view(), name='organization-accept-invite'),

    # Subscription Plans (Public & Admin)
    path('plans/', SubscriptionPlanListPublicApi.as_view(), name='billing-plans-public-list'),
    path('admin/plans/', SubscriptionPlanListCreateAdminApi.as_view(), name='billing-plans-admin-list-create'),
    path('admin/plans/<uuid:plan_id>/', SubscriptionPlanDetailAdminApi.as_view(), name='billing-plans-admin-detail'),

    # Paystack Billing & Transactions
    path('billing/initialize/', BillingInitializeApi.as_view(), name='billing-initialize'),
    path('billing/verify/', BillingVerifyApi.as_view(), name='billing-verify'),
    path('billing/transactions/', BillingTransactionsListApi.as_view(), name='billing-transactions-list'),
    path('billing/webhook/', PaystackWebhookPublicApi.as_view(), name='billing-paystack-webhook'),

    # Tenant lifecycle & metadata (Retrieve, Update PUT/PATCH, Delete, Deactivate, Reactivate)
    path('<uuid:organization_id>/deactivate/', OrganizationDeactivateApi.as_view(), name='organization-deactivate'),
    path('<uuid:organization_id>/reactivate/', OrganizationReactivateApi.as_view(), name='organization-reactivate'),
    path('<uuid:organization_id>/', OrganizationDetailApi.as_view(), name='organization-detail'),
]

