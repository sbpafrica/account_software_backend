from django.urls import path
from .admin import (
    ContractListCreateAdminApi,
    ContractDetailAdminApi,
    ContractProfitabilityAdminApi
)

urlpatterns = [
    path('admin/contracts/', ContractListCreateAdminApi.as_view(), name='contract-list-create-admin'),
    path('admin/contracts/<uuid:contract_id>/', ContractDetailAdminApi.as_view(), name='contract-detail-admin'),
    path('admin/contracts/<uuid:contract_id>/profitability/', ContractProfitabilityAdminApi.as_view(), name='contract-profitability-admin'),
]
