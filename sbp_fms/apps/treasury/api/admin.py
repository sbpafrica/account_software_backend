from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.treasury.selectors import (
    bank_account_list, bank_account_detail,
    bank_transaction_list, bank_transaction_detail,
    liquidity_forecast_get
)
from apps.treasury.services import TreasuryService
from apps.treasury.serializers import (
    BankAccountOutputSerializer, BankAccountCreateInputSerializer, BankAccountUpdateInputSerializer,
    BankTransactionOutputSerializer, BankTransactionCreateInputSerializer, BankTransactionUpdateInputSerializer,
    CashForecastOutputSerializer
)


class BankAccountListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')(), CountryScopedAccess]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Treasury - Accounts Admin'],
        operation_id='admin_treasury_bank_account_list',
        summary='List treasury bank accounts',
        description='Returns corporate bank accounts linked to General Ledger cash accounts.',
        parameters=[
            OpenApiParameter(name='country', description='Filter by country code (e.g. GH, CI)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: BankAccountOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        accounts = bank_account_list(country_code=request.query_params.get('country'))
        return paginate_queryset(accounts, request, BankAccountOutputSerializer)

    @extend_schema(
        tags=['Treasury - Accounts Admin'],
        operation_id='admin_treasury_bank_account_create',
        summary='Create bank account',
        description='Registers a new corporate bank account and links it to a GL cash account.',
        request=BankAccountCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: BankAccountOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        serializer = BankAccountCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            account = TreasuryService.bank_account_create(**serializer.validated_data)
            return api_success(
                data=BankAccountOutputSerializer(account).data,
                message="Bank account created successfully",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankAccountDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Accounts Admin'],
        operation_id='admin_treasury_bank_account_detail',
        summary='Retrieve bank account details',
        responses={
            status.HTTP_200_OK: BankAccountOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, account_id):
        account = bank_account_detail(account_id=account_id)
        return api_success(
            data=BankAccountOutputSerializer(account).data,
            message="Bank account retrieved successfully"
        )

    @extend_schema(
        tags=['Treasury - Accounts Admin'],
        operation_id='admin_treasury_bank_account_update',
        summary='Update bank account',
        request=BankAccountUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: BankAccountOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, account_id):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        serializer = BankAccountUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            account = TreasuryService.bank_account_update(account_id=account_id, **serializer.validated_data)
            return api_success(
                data=BankAccountOutputSerializer(account).data,
                message="Bank account updated successfully"
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Treasury - Accounts Admin'],
        operation_id='admin_treasury_bank_account_partial_update',
        summary='Partially update bank account',
        request=BankAccountUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: BankAccountOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, account_id):
        return self.put(request, account_id)

    @extend_schema(
        tags=['Treasury - Accounts Admin'],
        operation_id='admin_treasury_bank_account_delete',
        summary='Delete bank account',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, account_id):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        try:
            TreasuryService.bank_account_delete(account_id=account_id)
            return api_success(message="Bank account deleted successfully", status_code=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankTransactionListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_list',
        summary='List bank statement transactions',
        parameters=[
            OpenApiParameter(name='reconciled', description='Filter by reconciliation status (true/false)', required=False, type=bool),
            OpenApiParameter(name='account_id', description='Filter by BankAccount UUID', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        reconciled = request.query_params.get('reconciled')
        is_reconciled = None
        if reconciled is not None:
            is_reconciled = reconciled.lower() in ['true', '1']
        transactions = bank_transaction_list(
            is_reconciled=is_reconciled,
            bank_account_id=request.query_params.get('account_id')
        )
        return paginate_queryset(transactions, request, BankTransactionOutputSerializer)

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_create',
        summary='Record bank statement transaction',
        request=BankTransactionCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: BankTransactionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        serializer = BankTransactionCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tx = TreasuryService.bank_transaction_create(**serializer.validated_data)
            return api_success(
                data=BankTransactionOutputSerializer(tx).data,
                message="Bank transaction created successfully",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankTransactionDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_detail',
        summary='Retrieve bank transaction',
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, transaction_id):
        tx = bank_transaction_detail(transaction_id=transaction_id)
        return api_success(
            data=BankTransactionOutputSerializer(tx).data,
            message="Bank transaction retrieved successfully"
        )

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_update',
        summary='Update bank transaction',
        request=BankTransactionUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, transaction_id):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        serializer = BankTransactionUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tx = TreasuryService.bank_transaction_update(transaction_id=transaction_id, **serializer.validated_data)
            return api_success(
                data=BankTransactionOutputSerializer(tx).data,
                message="Bank transaction updated successfully"
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_partial_update',
        summary='Partially update bank transaction',
        request=BankTransactionUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, transaction_id):
        return self.put(request, transaction_id)

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_delete',
        summary='Delete bank transaction',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, transaction_id):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        try:
            TreasuryService.bank_transaction_delete(transaction_id=transaction_id)
            return api_success(message="Bank transaction deleted successfully", status_code=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankTransactionReconcileAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_bank_transaction_reconcile',
        summary='Reconcile bank transaction',
        description='Marks a bank statement line as reconciled against General Ledger cash transactions.',
        request=None,
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, transaction_id):
        tx = TreasuryService.reconcile_transaction(transaction_id=transaction_id)
        return api_success(
            data=BankTransactionOutputSerializer(tx).data,
            message="Bank transaction reconciled successfully"
        )


class CashForecastAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Forecast Admin'],
        operation_id='admin_treasury_cash_forecast',
        summary='Retrieve 30/60/90-day cash liquidity forecast',
        description='Aggregates available cash, pending customer receivables, and matched supplier payables.',
        responses={
            status.HTTP_200_OK: CashForecastOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        forecast = liquidity_forecast_get()
        return api_success(
            data=forecast,
            message="Cash forecast retrieved successfully"
        )
