from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.payroll_escrow.selectors import payroll_batch_list, payroll_batch_detail
from apps.payroll_escrow.services import PayrollEscrowService
from apps.payroll_escrow.serializers import (
    PayrollBatchOutputSerializer, PayrollBatchCreateInputSerializer, PayrollBatchUpdateInputSerializer
)


class PayrollBatchListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payroll:read')(), CountryScopedAccess]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_list',
        summary='List monthly payroll batches',
        description='Returns client workforce payroll batches with totals for net salaries, statutory taxes, and management fees.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code (e.g. GH, CI)', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by batch status (e.g. DRAFT, FUNDED, DISBURSED, BLOCKED_SHORTFALL)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: PayrollBatchOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        batches = payroll_batch_list(
            country_code=request.query_params.get('country'),
            status=request.query_params.get('status')
        )
        return paginate_queryset(batches, request, PayrollBatchOutputSerializer)

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_create',
        summary='Create monthly payroll batch',
        description='Creates a workforce payroll batch for a specified client and month/year.',
        request=PayrollBatchCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: PayrollBatchOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payroll:create'):
            return Response({'detail': 'Permission denied: payroll:create required'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PayrollBatchCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = PayrollEscrowService.payroll_batch_create(**serializer.validated_data)
        return api_success(
            data=PayrollBatchOutputSerializer(batch).data,
            message="Payroll batch created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class PayrollBatchDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payroll:read')()]

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_detail',
        summary='Retrieve payroll batch',
        responses={
            status.HTTP_200_OK: PayrollBatchOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, batch_id):
        batch = payroll_batch_detail(batch_id=batch_id)
        return api_success(data=PayrollBatchOutputSerializer(batch).data, message="Payroll batch retrieved successfully.")

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_update',
        summary='Update payroll batch',
        request=PayrollBatchUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: PayrollBatchOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, batch_id):
        if not request.user.has_permission_code('payroll:create'):
            return Response({'detail': 'Permission denied: payroll:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PayrollBatchUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = PayrollEscrowService.payroll_batch_update(batch_id=batch_id, **serializer.validated_data)
        return api_success(data=PayrollBatchOutputSerializer(batch).data, message="Payroll batch updated successfully.")

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_partial_update',
        summary='Partially update payroll batch',
        request=PayrollBatchUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: PayrollBatchOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, batch_id):
        return self.put(request, batch_id)

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_delete',
        summary='Delete payroll batch',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, batch_id):
        if not request.user.has_permission_code('payroll:create'):
            return Response({'detail': 'Permission denied: payroll:create required'}, status=status.HTTP_403_FORBIDDEN)
        PayrollEscrowService.payroll_batch_delete(batch_id=batch_id)
        return api_success(message="Payroll batch deleted successfully.", status_code=status.HTTP_200_OK)


class PayrollBatchDisburseAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payroll:disburse')()]

    @extend_schema(
        tags=['Payroll Escrow - Batches Admin'],
        operation_id='admin_payroll_batch_disburse',
        summary='Disburse payroll batch through solvency gatekeeper',
        description='Validates client escrow balance, generates double-entry disbursement journal, and releases payout.',
        request=None,
        responses={
            status.HTTP_200_OK: PayrollBatchOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, batch_id):
        batch = PayrollEscrowService.disburse_payroll_batch(batch_id=batch_id, user=request.user)
        return api_success(data=PayrollBatchOutputSerializer(batch).data, message="Payroll batch disbursed successfully.")

