from django.urls import path
from apps.ledger.api.public import AccountListPublicApi
from apps.ledger.api.admin import (
    AccountListAdminApi, AccountCreateAdminApi, AccountDetailAdminApi,
    JournalEntryListAdminApi, JournalEntryDetailAdminApi,
    JournalEntryPostAdminApi, JournalEntryReverseAdminApi,
    TrialBalanceAdminApi,
    CompanyProfileAdminApi, DepartmentListCreateAdminApi,
    CostCentreListCreateAdminApi,
    ProfitAndLossAdminApi, BalanceSheetAdminApi,
    CashFlowStatementAdminApi, GLAccountStatementAdminApi,
    CEOExecutiveDashboardAdminApi
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

    # Financial Reports
    path('admin/reports/profit-and-loss/', ProfitAndLossAdminApi.as_view(), name='profit-and-loss-admin'),
    path('admin/reports/balance-sheet/', BalanceSheetAdminApi.as_view(), name='balance-sheet-admin'),
    path('admin/reports/cash-flow/', CashFlowStatementAdminApi.as_view(), name='cash-flow-admin'),
    path('admin/reports/gl-statement/<uuid:account_id>/', GLAccountStatementAdminApi.as_view(), name='gl-account-statement-admin'),
    path('admin/reports/ceo-dashboard/', CEOExecutiveDashboardAdminApi.as_view(), name='ceo-dashboard-admin'),

    # Company Profile & Dimensions
    path('admin/company-profile/', CompanyProfileAdminApi.as_view(), name='company-profile-admin'),
    path('admin/departments/', DepartmentListCreateAdminApi.as_view(), name='department-list-create-admin'),
    path('admin/cost-centres/', CostCentreListCreateAdminApi.as_view(), name='cost-centre-list-create-admin'),
]

