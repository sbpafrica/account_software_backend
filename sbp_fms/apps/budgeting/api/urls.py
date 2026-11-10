from django.urls import path
from .admin import (
    BudgetListCreateAdminApi,
    BudgetDetailAdminApi,
    BudgetSubmitAdminApi,
    BudgetApproveAdminApi,
    BudgetVarianceReportAdminApi,
    PreCommitmentCheckAdminApi
)

urlpatterns = [
    path('admin/budgets/', BudgetListCreateAdminApi.as_view(), name='budget-list-create-admin'),
    path('admin/budgets/<uuid:budget_id>/', BudgetDetailAdminApi.as_view(), name='budget-detail-admin'),
    path('admin/budgets/<uuid:budget_id>/submit/', BudgetSubmitAdminApi.as_view(), name='budget-submit-admin'),
    path('admin/budgets/<uuid:budget_id>/approve/', BudgetApproveAdminApi.as_view(), name='budget-approve-admin'),
    path('admin/budgets/<uuid:budget_id>/variance/', BudgetVarianceReportAdminApi.as_view(), name='budget-variance-admin'),
    path('admin/pre-commitment-check/', PreCommitmentCheckAdminApi.as_view(), name='budget-pre-commitment-check-admin'),
]
