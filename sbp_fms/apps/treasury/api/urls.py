from django.urls import path
from apps.treasury.api.public import BankWebhookPublicApi
from apps.treasury.api.admin import (
    BankAccountListAdminApi, BankAccountDetailAdminApi,
    BankTransactionListAdminApi, BankTransactionDetailAdminApi, BankTransactionReconcileAdminApi,
    CashForecastAdminApi, CashbookAdminApi,
    BankStatementListAdminApi, BankStatementImportAdminApi, BankStatementDetailAdminApi,
    BankReconciliationSummaryAdminApi, BankReconciliationAutoMatchAdminApi,
    BankReconciliationManualMatchAdminApi, BankReconciliationManualUnmatchAdminApi,
    BankReconciliationAdjustmentAdminApi, BankReconciliationListCreateAdminApi,
    BankReconciliationDetailAdminApi, BankReconciliationFinalizeAdminApi,
    BankFeedConfigureAdminApi, BankFeedSyncAdminApi,
    BankFeedConnectSessionAdminApi, BankFeedExchangeTokenAdminApi, BankFeedDisconnectAdminApi
)

urlpatterns = [
    # Public Banking Webhook
    path('public/webhook/', BankWebhookPublicApi.as_view(), name='bank-webhook-public'),

    # Admin / Accounts
    path('admin/accounts/', BankAccountListAdminApi.as_view(), name='bank-account-list-admin'),
    path('admin/accounts/<uuid:account_id>/', BankAccountDetailAdminApi.as_view(), name='bank-account-detail-admin'),

    # Admin / Cashbook
    path('admin/cashbook/', CashbookAdminApi.as_view(), name='treasury-cashbook-admin'),

    # Admin / Bank Statements
    path('admin/statements/', BankStatementListAdminApi.as_view(), name='bank-statement-list-admin'),
    path('admin/statements/import/', BankStatementImportAdminApi.as_view(), name='bank-statement-import-admin'),
    path('admin/statements/<uuid:statement_id>/', BankStatementDetailAdminApi.as_view(), name='bank-statement-detail-admin'),

    # Admin / Bank Reconciliation Engine
    path('admin/reconciliation/summary/', BankReconciliationSummaryAdminApi.as_view(), name='bank-reconciliation-summary-admin'),
    path('admin/reconciliation/auto-match/', BankReconciliationAutoMatchAdminApi.as_view(), name='bank-reconciliation-auto-match-admin'),
    path('admin/reconciliation/manual-match/', BankReconciliationManualMatchAdminApi.as_view(), name='bank-reconciliation-manual-match-admin'),
    path('admin/reconciliation/manual-unmatch/<uuid:line_id>/', BankReconciliationManualUnmatchAdminApi.as_view(), name='bank-reconciliation-manual-unmatch-admin'),
    path('admin/reconciliation/adjust/', BankReconciliationAdjustmentAdminApi.as_view(), name='bank-reconciliation-adjust-admin'),
    path('admin/reconciliations/', BankReconciliationListCreateAdminApi.as_view(), name='bank-reconciliation-list-create-admin'),
    path('admin/reconciliations/<uuid:reconciliation_id>/', BankReconciliationDetailAdminApi.as_view(), name='bank-reconciliation-detail-admin'),
    path('admin/reconciliations/<uuid:reconciliation_id>/finalize/', BankReconciliationFinalizeAdminApi.as_view(), name='bank-reconciliation-finalize-admin'),

    # Admin / Legacy Transactions & Reconciliation
    path('admin/transactions/', BankTransactionListAdminApi.as_view(), name='bank-transactions-admin'),
    path('admin/transactions/<uuid:transaction_id>/', BankTransactionDetailAdminApi.as_view(), name='bank-transaction-detail-admin'),
    path('admin/transactions/<uuid:transaction_id>/reconcile/', BankTransactionReconcileAdminApi.as_view(), name='bank-transaction-reconcile-admin'),

    # Admin / Cash Forecast
    path('admin/forecast/', CashForecastAdminApi.as_view(), name='cash-forecast-admin'),

    # Admin / Direct & Open Banking Feed (Mono / FNB)
    path('admin/accounts/<uuid:bank_account_id>/feed-session/', BankFeedConnectSessionAdminApi.as_view(), name='bank-feed-session-admin'),
    path('admin/accounts/<uuid:bank_account_id>/feed-exchange/', BankFeedExchangeTokenAdminApi.as_view(), name='bank-feed-exchange-admin'),
    path('admin/accounts/<uuid:bank_account_id>/feed-disconnect/', BankFeedDisconnectAdminApi.as_view(), name='bank-feed-disconnect-admin'),
    path('admin/accounts/<uuid:bank_account_id>/feed-config/', BankFeedConfigureAdminApi.as_view(), name='bank-feed-configure-admin'),
    path('admin/accounts/<uuid:bank_account_id>/sync-feed/', BankFeedSyncAdminApi.as_view(), name='bank-feed-sync-admin'),
]
