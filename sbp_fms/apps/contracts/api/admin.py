from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode
from apps.contracts.selectors import contract_list, contract_detail, contract_profitability_get
from apps.contracts.services import ContractService
from apps.contracts.serializers import (
    ContractCreateInputSerializer, ContractUpdateInputSerializer,
    ContractOutputSerializer, ContractProfitabilityOutputSerializer
)


class ContractListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Contracts & Profitability'],
        summary='List client contracts',
        parameters=[
            OpenApiParameter('client_id', str, required=False),
            OpenApiParameter('status', str, required=False),
        ],
        responses={200: ContractOutputSerializer(many=True)}
    )
    def get(self, request):
        contracts = contract_list(
            client_id=request.query_params.get('client_id'),
            status=request.query_params.get('status')
        )
        return paginate_queryset(contracts, request, ContractOutputSerializer)

    @extend_schema(
        tags=['Contracts & Profitability'],
        summary='Create new contract',
        request=ContractCreateInputSerializer,
        responses={201: ContractOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ContractCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        contract = ContractService.contract_create(
            contract_number=data['contract_number'],
            client_id=str(data['client_id']),
            title=data['title'],
            start_date=data['start_date'],
            end_date=data.get('end_date'),
            total_contract_value=data.get('total_contract_value'),
            cost_centre=data.get('cost_centre', ''),
            notes=data.get('notes', '')
        )
        return api_success(data=ContractOutputSerializer(contract).data, message="Contract created successfully.", status_code=status.HTTP_201_CREATED)


class ContractDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(tags=['Contracts & Profitability'], summary='Get contract details', responses={200: ContractOutputSerializer})
    def get(self, request, contract_id):
        contract = contract_detail(contract_id=str(contract_id))
        return api_success(data=ContractOutputSerializer(contract).data)

    @extend_schema(
        tags=['Contracts & Profitability'],
        summary='Update contract',
        description='Update contract dates, commercial value, cost centre, or notes.',
        request=ContractUpdateInputSerializer,
        responses={200: ContractOutputSerializer}
    )
    def patch(self, request, contract_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ContractUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = ContractService.contract_update(contract_id=str(contract_id), **serializer.validated_data)
        return api_success(data=ContractOutputSerializer(contract).data, message="Contract updated.")


class ContractProfitabilityAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Contracts & Profitability'],
        summary='Get contract revenue, direct workforce, expenses and profitability',
        responses={200: ContractProfitabilityOutputSerializer}
    )
    def get(self, request, contract_id):
        analysis = contract_profitability_get(contract_id=str(contract_id))
        return api_success(data=analysis, message="Contract profitability analyzed.")
