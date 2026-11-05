from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.payroll_escrow.selectors import payroll_batch_list, payroll_batch_detail
from apps.payroll_escrow.services import PayrollEscrowService
from apps.payroll_escrow.serializers import PayrollBatchOutputSerializer, PayrollBatchCreateInputSerializer

class PayrollBatchListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payroll:read')(), CountryScopedAccess]

    def get(self, request):
        batches = payroll_batch_list(
            country_code=request.query_params.get('country'),
            status=request.query_params.get('status')
        )
        return Response(PayrollBatchOutputSerializer(batches, many=True).data)

    def post(self, request):
        self.check_permissions(request)
        if not request.user.has_permission_code('payroll:create'):
            return Response({'detail': 'Permission denied: payroll:create required'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PayrollBatchCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = PayrollEscrowService.payroll_batch_create(**serializer.validated_data)
        return Response(PayrollBatchOutputSerializer(batch).data, status=status.HTTP_201_CREATED)

class PayrollBatchDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payroll:read')()]

    def get(self, request, batch_id):
        batch = payroll_batch_detail(batch_id=batch_id)
        return Response(PayrollBatchOutputSerializer(batch).data)

class PayrollBatchDisburseAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payroll:disburse')()]

    def post(self, request, batch_id):
        batch = PayrollEscrowService.disburse_payroll_batch(batch_id=batch_id, user=request.user)
        return Response(PayrollBatchOutputSerializer(batch).data)
