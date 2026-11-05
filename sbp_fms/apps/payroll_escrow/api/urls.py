from django.urls import path
from apps.payroll_escrow.api.public import ClientEscrowBalancePublicApi
from apps.payroll_escrow.api.admin import (
    PayrollBatchListAdminApi, PayrollBatchDetailAdminApi, PayrollBatchDisburseAdminApi
)

urlpatterns = [
    # Public Client Facing
    path('public/client-balance/<uuid:client_id>/', ClientEscrowBalancePublicApi.as_view(), name='payroll-client-balance-public'),

    # Admin / Finance Operations
    path('admin/batches/', PayrollBatchListAdminApi.as_view(), name='payroll-batch-list-admin'),
    path('admin/batches/<uuid:batch_id>/', PayrollBatchDetailAdminApi.as_view(), name='payroll-batch-detail-admin'),
    path('admin/batches/<uuid:batch_id>/disburse/', PayrollBatchDisburseAdminApi.as_view(), name='payroll-batch-disburse-admin'),
]
