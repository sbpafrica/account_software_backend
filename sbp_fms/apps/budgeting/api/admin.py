from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode
from apps.budgeting.selectors import (
    budget_list, budget_detail, budget_variance_report_get, budget_pre_commitment_check
)
from apps.budgeting.services import BudgetingService
from apps.budgeting.serializers import (
    BudgetCreateInputSerializer, BudgetOutputSerializer, PreCommitmentCheckInputSerializer,
    BudgetVarianceReportOutputSerializer, PreCommitmentCheckOutputSerializer
)


class BudgetListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Budgeting & Commitments'],
        summary='List budgets',
        parameters=[
            OpenApiParameter('financial_year', int, required=False),
            OpenApiParameter('department', str, required=False),
            OpenApiParameter('status', str, required=False),
        ],
        responses={200: BudgetOutputSerializer(many=True)}
    )
    def get(self, request):
        year = request.query_params.get('financial_year')
        dept = request.query_params.get('department')
        b_status = request.query_params.get('status')
        budgets = budget_list(
            financial_year=int(year) if year else None,
            department=dept,
            status=b_status
        )
        return paginate_queryset(budgets, request, BudgetOutputSerializer)

    @extend_schema(
        tags=['Budgeting & Commitments'],
        summary='Create new budget',
        request=BudgetCreateInputSerializer,
        responses={201: BudgetOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('ledger:post'):
            return Response({'detail': 'Permission denied: ledger:post required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = BudgetCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        budget = BudgetingService.budget_create(
            name=data['name'],
            financial_year=data['financial_year'],
            department=data.get('department', ''),
            cost_centre=data.get('cost_centre', ''),
            notes=data.get('notes', ''),
            lines_data=data.get('lines', []),
            user=request.user
        )
        return api_success(data=BudgetOutputSerializer(budget).data, message="Budget created successfully.", status_code=status.HTTP_201_CREATED)


class BudgetDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(tags=['Budgeting & Commitments'], summary='Get budget details', responses={200: BudgetOutputSerializer})
    def get(self, request, budget_id):
        budget = budget_detail(budget_id=str(budget_id))
        return api_success(data=BudgetOutputSerializer(budget).data)


class BudgetSubmitAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:post')()]

    @extend_schema(
        tags=['Budgeting & Commitments'],
        summary='Submit budget for approval',
        description='Submits a DRAFT budget to SUBMITTED status for financial management review.',
        request=None,
        responses={200: BudgetOutputSerializer}
    )
    def post(self, request, budget_id):
        budget = BudgetingService.budget_submit(budget_id=str(budget_id))
        return api_success(data=BudgetOutputSerializer(budget).data, message="Budget submitted for approval.")


class BudgetApproveAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:post')()]

    @extend_schema(
        tags=['Budgeting & Commitments'],
        summary='Approve budget',
        description='Approves an active budget, establishing financial ceiling constraints for cost centres and departments.',
        request=None,
        responses={200: BudgetOutputSerializer}
    )
    def post(self, request, budget_id):
        budget = BudgetingService.budget_approve(budget_id=str(budget_id), user=request.user)
        return api_success(data=BudgetOutputSerializer(budget).data, message="Budget approved.")


class BudgetVarianceReportAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Budgeting & Commitments'],
        summary='Get budget vs actuals vs commitments variance report',
        description='Generates three-way budget variance report comparing planned allocation against posted GL actuals and committed payment vouchers.',
        responses={200: BudgetVarianceReportOutputSerializer}
    )
    def get(self, request, budget_id):
        report = budget_variance_report_get(budget_id=str(budget_id))
        return api_success(data=report, message="Budget variance report retrieved.")


class PreCommitmentCheckAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Budgeting & Commitments'],
        summary='Execute pre-commitment budget availability check',
        description='Intercepts purchase requisitions and payment vouchers to check if required funds exist within the approved budget line.',
        request=PreCommitmentCheckInputSerializer,
        responses={200: PreCommitmentCheckOutputSerializer}
    )
    def post(self, request):
        serializer = PreCommitmentCheckInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = budget_pre_commitment_check(
            account_id=str(data['account_id']),
            amount=data['amount'],
            department=data.get('department'),
            cost_centre=data.get('cost_centre'),
            financial_year=data.get('financial_year')
        )
        return api_success(data=result, message="Pre-commitment check executed.")
