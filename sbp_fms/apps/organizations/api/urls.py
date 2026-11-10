from django.urls import path
from .views import (
    OrganizationRegisterPublicApi,
    OrganizationMeListApi,
    OrganizationSwitchApi,
    OrganizationInviteApi,
    OrganizationAcceptInviteApi,
    OrganizationDetailApi,
    SubscriptionPlanListPublicApi,
    SubscriptionPlanListCreateAdminApi,
    SubscriptionPlanDetailAdminApi,
    BillingInitializeApi,
    BillingVerifyApi,
    BillingTransactionsListApi,
    PaystackWebhookPublicApi,
)

urlpatterns = [
    # Public self-service SaaS onboarding
    path('register/', OrganizationRegisterPublicApi.as_view(), name='organization-register-public'),

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

    # Tenant metadata & settings
    path('<uuid:organization_id>/', OrganizationDetailApi.as_view(), name='organization-detail'),
]
