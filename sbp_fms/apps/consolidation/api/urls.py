from django.urls import path
from .admin import (
    ExchangeRateListCreateAdminApi,
    ExchangeRateLiveAdminApi,
    FXRevaluationRunAdminApi,
    ConsolidatedTrialBalanceAdminApi
)

urlpatterns = [
    path('admin/rates/', ExchangeRateListCreateAdminApi.as_view(), name='exchange-rate-list-create-admin'),
    path('admin/rates/live/', ExchangeRateLiveAdminApi.as_view(), name='exchange-rate-live-admin'),
    path('admin/revaluations/', FXRevaluationRunAdminApi.as_view(), name='fx-revaluation-run-admin'),
    path('admin/trial-balance/', ConsolidatedTrialBalanceAdminApi.as_view(), name='consolidated-trial-balance-admin'),
]
