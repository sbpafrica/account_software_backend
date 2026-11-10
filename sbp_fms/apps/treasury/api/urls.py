from django.urls import path
from apps.treasury.api.public import BankWebhookPublicApi
from apps.treasury.api.admin import (
    BankAccountListAdminApi, BankAccountDetailAdminApi,
    BankTransactionListAdminApi, BankTransactionDetailAdminApi, BankTransactionReconcileAdminApi,
    CashForecastAdminApi
)

urlpatterns = [
    # Public Banking Webhook
    path('public/webhook/', BankWebhookPublicApi.as_view(), name='bank-webhook-public'),

    # Admin / Accounts
    path('admin/accounts/', BankAccountListAdminApi.as_view(), name='bank-account-list-admin'),
    path('admin/accounts/<uuid:account_id>/', BankAccountDetailAdminApi.as_view(), name='bank-account-detail-admin'),

    # Admin / Transactions & Reconciliation
    path('admin/transactions/', BankTransactionListAdminApi.as_view(), name='bank-transactions-admin'),
    path('admin/transactions/<uuid:transaction_id>/', BankTransactionDetailAdminApi.as_view(), name='bank-transaction-detail-admin'),
    path('admin/transactions/<uuid:transaction_id>/reconcile/', BankTransactionReconcileAdminApi.as_view(), name='bank-transaction-reconcile-admin'),

    # Admin / Cash Forecast
    path('admin/forecast/', CashForecastAdminApi.as_view(), name='cash-forecast-admin'),
]
