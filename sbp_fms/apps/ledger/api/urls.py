from django.urls import path
from apps.ledger.api.public import AccountListPublicApi
from apps.ledger.api.admin import (
    AccountListAdminApi, AccountCreateAdminApi, AccountDetailAdminApi,
    JournalEntryListAdminApi, JournalEntryDetailAdminApi,
    JournalEntryPostAdminApi, JournalEntryReverseAdminApi,
    TrialBalanceAdminApi
)

urlpatterns = [
    # Public Endpoints
    path('public/accounts/', AccountListPublicApi.as_view(), name='account-list-public'),

    # Admin / Finance Endpoints
    path('admin/accounts/', AccountListAdminApi.as_view(), name='account-list-admin'),
    path('admin/accounts/create/', AccountCreateAdminApi.as_view(), name='account-create-admin'),
    path('admin/accounts/<uuid:account_id>/', AccountDetailAdminApi.as_view(), name='account-detail-admin'),

    path('admin/entries/', JournalEntryListAdminApi.as_view(), name='entry-list-admin'),
    path('admin/entries/post/', JournalEntryPostAdminApi.as_view(), name='entry-post-admin'),
    path('admin/entries/<uuid:entry_id>/', JournalEntryDetailAdminApi.as_view(), name='entry-detail-admin'),
    path('admin/entries/<uuid:entry_id>/reverse/', JournalEntryReverseAdminApi.as_view(), name='entry-reverse-admin'),
    path('admin/trial-balance/', TrialBalanceAdminApi.as_view(), name='trial-balance-admin'),
]
