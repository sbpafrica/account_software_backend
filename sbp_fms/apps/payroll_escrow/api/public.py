from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.common.responses import api_success
from apps.payroll_escrow.selectors import client_escrow_balance_get
from apps.payroll_escrow.serializers import ClientEscrowBalanceOutputSerializer


class ClientEscrowBalancePublicApi(APIView):
    """[PUBLIC API]: Clients check their available escrow deposit balance."""
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Payroll Escrow - Public'],
        operation_id='public_payroll_escrow_client_balance',
        summary='Retrieve client escrow balance',
        description='Returns available client funding escrow balance, cached for performance.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code filter (e.g. GH, CI)', required=False, type=str, default='GH')
        ],
        responses={
            status.HTTP_200_OK: ClientEscrowBalanceOutputSerializer,
        }
    )
    def get(self, request, client_id):
        country = request.query_params.get('country', 'GH')
        balance = client_escrow_balance_get(client_id=client_id, country_code=country)
        payload = {'client_id': str(client_id), 'available_escrow_balance': balance}
        return api_success(data=payload, message="Client escrow balance retrieved successfully.")

