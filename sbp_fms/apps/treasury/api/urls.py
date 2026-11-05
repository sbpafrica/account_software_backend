from django.urls import path
from apps.treasury.api.public import BankWebhookPublicApi
from apps.treasury.api.admin import (
    BankAccountListAdminApi, CashForecastAdminApi, BankTransactionListAdminApi
)

urlpatterns = [
    path('public/webhook/', BankWebhookPublicApi.as_view(), name='bank-webhook-public'),
    path('admin/accounts/', BankAccountListAdminApi.as_view(), name='bank-account-list-admin'),
    path('admin/forecast/', CashForecastAdminApi.as_view(), name='cash-forecast-admin'),
    path('admin/transactions/', BankTransactionListAdminApi.as_view(), name='bank-transactions-admin'),
]
