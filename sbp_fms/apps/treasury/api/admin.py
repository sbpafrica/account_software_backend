from decimal import Decimal
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success, api_error
from apps.common.idempotency import idempotent_endpoint
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.treasury.selectors import (
    bank_account_list, bank_account_detail,
    bank_transaction_list, bank_transaction_detail,
    cashbook_get, bank_statement_list, bank_statement_detail,
    bank_reconciliation_list, bank_reconciliation_detail, bank_reconciliation_summary,
    liquidity_forecast_get
)
from apps.treasury.services import TreasuryService
from apps.treasury.serializers import (
    BankAccountOutputSerializer, BankAccountCreateInputSerializer, BankAccountUpdateInputSerializer,
    BankTransactionOutputSerializer, BankTransactionCreateInputSerializer, BankTransactionUpdateInputSerializer,
    CashForecastOutputSerializer, CashbookOutputSerializer,
    BankStatementOutputSerializer, BankStatementImportInputSerializer, BankStatementLineOutputSerializer,
    BankReconciliationSummaryOutputSerializer, BankReconciliationOutputSerializer,
    ReconciliationAutoMatchInputSerializer, ReconciliationAutoMatchOutputSerializer,
    ReconciliationManualMatchInputSerializer, ReconciliationAdjustmentJournalInputSerializer,
    BankReconciliationSaveInputSerializer
)


# ============================================================================
# 1. BANK ACCOUNTS
# ============================================================================

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
        description='Partially update bank account configuration such as status, branch, or currency.',
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


# ============================================================================
# 2. CASHBOOK REPORT
# ============================================================================

class CashbookAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Cashbook'],
        operation_id='admin_treasury_cashbook',
        summary='Retrieve Cashbook report with running balance',
        description='Returns receipts and payments affecting bank/cash accounts with dynamic running balances.',
        parameters=[
            OpenApiParameter(name='bank_account_id', description='Filter by BankAccount UUID', required=False, type=str),
            OpenApiParameter(name='gl_account_id', description='Filter by General Ledger Account UUID', required=False, type=str),
            OpenApiParameter(name='start_date', description='Start date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='end_date', description='End date (YYYY-MM-DD)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: CashbookOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        bank_account_id = request.query_params.get('bank_account_id')
        gl_account_id = request.query_params.get('gl_account_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        cashbook = cashbook_get(
            bank_account_id=bank_account_id,
            gl_account_id=gl_account_id,
            start_date=start_date,
            end_date=end_date
        )
        return api_success(data=cashbook, message="Cashbook report retrieved successfully.")


# ============================================================================
# 3. BANK STATEMENTS & UPLOAD / IMPORT
# ============================================================================

class BankStatementListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Treasury - Bank Statements'],
        operation_id='admin_treasury_bank_statement_list',
        summary='List imported bank statements',
        parameters=[
            OpenApiParameter(name='bank_account_id', description='Filter by BankAccount UUID', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: BankStatementOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        bank_account_id = request.query_params.get('bank_account_id')
        statements = bank_statement_list(bank_account_id=bank_account_id)
        return paginate_queryset(statements, request, BankStatementOutputSerializer)


class BankStatementImportAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:write')()]

    @extend_schema(
        tags=['Treasury - Bank Statements'],
        operation_id='admin_treasury_bank_statement_import',
        summary='Import bank statement (CSV or JSON lines)',
        description='Uploads and parses bank statement records with automated duplicate hash detection.',
        request=BankStatementImportInputSerializer,
        responses={
            status.HTTP_201_CREATED: BankStatementOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = BankStatementImportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            stmt = TreasuryService.bank_statement_import(
                bank_account_id=data['bank_account_id'],
                statement_date=data.get('statement_date'),
                file_name=data.get('file_name', ''),
                csv_content=data.get('csv_content'),
                lines_data=data.get('lines'),
                opening_balance=data.get('opening_balance', Decimal('0.0000')),
                closing_balance=data.get('closing_balance', Decimal('0.0000')),
                user=request.user
            )
            return api_success(
                data=BankStatementOutputSerializer(stmt).data,
                message=f"Bank statement imported successfully with {stmt.total_lines} lines.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankStatementDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Bank Statements'],
        operation_id='admin_treasury_bank_statement_detail',
        summary='Retrieve bank statement details with all lines',
        responses={
            status.HTTP_200_OK: BankStatementOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, statement_id):
        stmt = bank_statement_detail(statement_id=statement_id)
        return api_success(data=BankStatementOutputSerializer(stmt).data)


# ============================================================================
# 4. BANK RECONCILIATION ENGINE
# ============================================================================

class BankReconciliationSummaryAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Bank Reconciliation'],
        operation_id='admin_treasury_bank_reconciliation_summary',
        summary='Generate two-way Bank Reconciliation statement summary',
        description='Computes balance per bank, deposits in transit, outstanding cheques, and adjusted book balance.',
        parameters=[
            OpenApiParameter(name='bank_account_id', description='BankAccount UUID', required=True, type=str),
            OpenApiParameter(name='statement_date', description='As-of statement date (YYYY-MM-DD)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: BankReconciliationSummaryOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        bank_account_id = request.query_params.get('bank_account_id')
        if not bank_account_id:
            raise exceptions.ValidationError({'detail': 'bank_account_id is required.'})

        stmt_date_str = request.query_params.get('statement_date')
        statement_date = datetime.strptime(stmt_date_str, '%Y-%m-%d').date() if stmt_date_str else None

        summary = bank_reconciliation_summary(
            bank_account_id=bank_account_id,
            statement_date=statement_date
        )
        return api_success(data=summary, message="Reconciliation summary generated successfully.")


class BankReconciliationAutoMatchAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Bank Reconciliation'],
        operation_id='admin_treasury_bank_reconciliation_auto_match',
        summary='Auto-match unreconciled bank statement lines against GL journal lines',
        request=ReconciliationAutoMatchInputSerializer,
        responses={
            status.HTTP_200_OK: ReconciliationAutoMatchOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = ReconciliationAutoMatchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = TreasuryService.reconciliation_auto_match(
            bank_account_id=data['bank_account_id'],
            tolerance_days=data.get('tolerance_days', 3),
            user=request.user
        )
        return api_success(
            data=result,
            message=f"Auto-match completed: {result['matched_count']} lines matched successfully."
        )


class BankReconciliationManualMatchAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Bank Reconciliation'],
        operation_id='admin_treasury_bank_reconciliation_manual_match',
        summary='Manually match a statement line to a GL journal line',
        request=ReconciliationManualMatchInputSerializer,
        responses={
            status.HTTP_200_OK: BankStatementLineOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = ReconciliationManualMatchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            line = TreasuryService.reconciliation_manual_match(
                statement_line_id=data['statement_line_id'],
                journal_line_id=data['journal_line_id'],
                user=request.user
            )
            return api_success(
                data=BankStatementLineOutputSerializer(line).data,
                message="Statement line matched to journal line successfully."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankReconciliationManualUnmatchAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Reconciliation Admin'],
        operation_id='admin_treasury_reconciliation_manual_unmatch',
        summary='Unmatch previously matched bank statement line',
        description='Removes reconciliation link between a bank statement line and journal line, restoring unmatched status.',
        request=None,
        responses={
            status.HTTP_200_OK: BankStatementLineOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, line_id):
        try:
            line = TreasuryService.reconciliation_manual_unmatch(
                statement_line_id=line_id,
                user=request.user
            )
            return api_success(
                data=BankStatementLineOutputSerializer(line).data,
                message="Statement line unmatched successfully."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankReconciliationAdjustmentAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Bank Reconciliation'],
        operation_id='admin_treasury_bank_reconciliation_adjustment',
        summary='Post GL adjustment journal for bank fees or interest directly from statement line',
        request=ReconciliationAdjustmentJournalInputSerializer,
        responses={
            status.HTTP_201_CREATED: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = ReconciliationAdjustmentJournalInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            journal_line = TreasuryService.reconciliation_create_adjustment_journal(
                statement_line_id=data['statement_line_id'],
                offset_account_id=data['offset_account_id'],
                description=data.get('description', ''),
                user=request.user
            )
            return api_success(
                data={'journal_line_id': str(journal_line.id), 'entry_number': journal_line.entry.entry_number},
                message="Bank adjustment journal posted and statement line reconciled.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankReconciliationListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Treasury - Bank Reconciliation'],
        operation_id='admin_treasury_bank_reconciliation_list',
        summary='List reconciliation records',
        parameters=[
            OpenApiParameter(name='bank_account_id', description='Filter by BankAccount UUID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by status (DRAFT/COMPLETED)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: BankReconciliationOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        bank_account_id = request.query_params.get('bank_account_id')
        rec_status = request.query_params.get('status')
        reconciliations = bank_reconciliation_list(bank_account_id=bank_account_id, status=rec_status)
        return paginate_queryset(reconciliations, request, BankReconciliationOutputSerializer)

    @extend_schema(
        tags=['Treasury - Bank Reconciliation'],
        operation_id='admin_treasury_bank_reconciliation_create',
        summary='Save a formal Bank Reconciliation snapshot',
        request=BankReconciliationSaveInputSerializer,
        responses={
            status.HTTP_201_CREATED: BankReconciliationOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('treasury:reconcile'):
            raise exceptions.PermissionDenied('Permission denied: treasury:reconcile required')
        serializer = BankReconciliationSaveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        statement_date = data.get('statement_date') or datetime.now().date()
        summary = bank_reconciliation_summary(bank_account_id=data['bank_account_id'], statement_date=statement_date)

        try:
            rec = TreasuryService.reconciliation_record_save(
                bank_account_id=data['bank_account_id'],
                statement_date=statement_date,
                summary_data=summary,
                user=request.user,
                notes=data.get('notes', '')
            )
            return api_success(
                data=BankReconciliationOutputSerializer(rec).data,
                message="Bank reconciliation snapshot saved successfully.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankReconciliationDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Reconciliation Admin'],
        operation_id='admin_treasury_reconciliation_detail',
        summary='Retrieve bank reconciliation session details',
        description='Fetch saved bank reconciliation session snapshot and summary statistics by reconciliation UUID.',
        responses={status.HTTP_200_OK: BankReconciliationOutputSerializer}
    )
    def get(self, request, reconciliation_id):
        rec = bank_reconciliation_detail(reconciliation_id=reconciliation_id)
        return api_success(data=BankReconciliationOutputSerializer(rec).data)


class BankReconciliationFinalizeAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Reconciliation Admin'],
        operation_id='admin_treasury_reconciliation_finalize',
        summary='Finalize and close bank reconciliation session',
        description='Locks and finalizes a bank reconciliation run, verifying zero unreconciled variance before closing the period.',
        request=None,
        responses={
            status.HTTP_200_OK: BankReconciliationOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, reconciliation_id):
        try:
            rec = TreasuryService.reconciliation_finalize(
                reconciliation_id=reconciliation_id,
                user=request.user
            )
            return api_success(
                data=BankReconciliationOutputSerializer(rec).data,
                message="Bank reconciliation finalized successfully."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


# ============================================================================
# 5. TRANSACTIONS & LIQUIDITY FORECAST
# ============================================================================

class BankTransactionListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_transaction_list',
        summary='List bank transactions',
        description='Retrieve paginated list of bank transactions with optional filtering by bank account UUID and reconciliation status.',
        parameters=[
            OpenApiParameter(name='account_id', description='Filter by bank account UUID', required=False, type=str),
            OpenApiParameter(name='reconciled', description='Filter by reconciled boolean (true/false)', required=False, type=bool),
        ],
        responses={status.HTTP_200_OK: BankTransactionOutputSerializer(many=True)}
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
        operation_id='admin_treasury_transaction_create',
        summary='Create bank transaction',
        description='Create a new bank transaction entry (deposit or withdrawal) for treasury ledger tracking.',
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
        operation_id='admin_treasury_transaction_detail',
        summary='Retrieve bank transaction details',
        description='Fetch full bank transaction details including amount, type, reference, and reconciliation status.',
        responses={status.HTTP_200_OK: BankTransactionOutputSerializer}
    )
    def get(self, request, transaction_id):
        tx = bank_transaction_detail(transaction_id=transaction_id)
        return api_success(data=BankTransactionOutputSerializer(tx).data)

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_transaction_update',
        summary='Update bank transaction',
        description='Update transaction description, reference number, or counterparty details.',
        request=BankTransactionUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def put(self, request, transaction_id):
        if not request.user.has_permission_code('treasury:write'):
            raise exceptions.PermissionDenied('Permission denied: treasury:write required')
        serializer = BankTransactionUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tx = TreasuryService.bank_transaction_update(transaction_id=transaction_id, **serializer.validated_data)
            return api_success(data=BankTransactionOutputSerializer(tx).data, message="Bank transaction updated successfully")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_transaction_partial_update',
        summary='Partially update bank transaction',
        description='Partially update mutable fields of an unreconciled bank transaction.',
        request=BankTransactionUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def patch(self, request, transaction_id):
        return self.put(request, transaction_id)

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_transaction_delete',
        summary='Delete bank transaction',
        description='Delete an unreconciled bank transaction.',
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
            return api_success(message="Bank transaction deleted successfully")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class BankTransactionReconcileAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Transactions Admin'],
        operation_id='admin_treasury_transaction_reconcile',
        summary='Mark bank transaction as reconciled',
        description='Manually mark a bank transaction as reconciled against matched records.',
        request=None,
        responses={
            status.HTTP_200_OK: BankTransactionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, transaction_id):
        tx = TreasuryService.reconcile_transaction(transaction_id=transaction_id)
        return api_success(data=BankTransactionOutputSerializer(tx).data, message="Bank transaction reconciled successfully")


class CashForecastAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Treasury - Forecasting'],
        operation_id='admin_treasury_cash_forecast',
        summary='Retrieve 30/60/90-day cash & liquidity forecast',
        description='Computes current cash position and projects 30, 60, and 90-day expected inflows (AR invoices) and outflows (AP bills and expenses).',
        responses={
            status.HTTP_200_OK: CashForecastOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        forecast = liquidity_forecast_get()
        return api_success(data=forecast, message="Cash forecast retrieved successfully")


# ============================================================================
# 7. DIRECT & OPEN BANKING FEED INTEGRATION (MONO / FNB)
# ============================================================================

from apps.treasury.bank_feed import BankFeedService
from apps.treasury.serializers import (
    BankFeedConfigureInputSerializer, BankFeedConnectionOutputSerializer,
    BankFeedSyncInputSerializer, BankFeedSyncOutputSerializer,
    BankFeedConnectSessionOutputSerializer, BankFeedExchangeTokenInputSerializer
)


class BankFeedConnectSessionAdminApi(APIView):
    """
    [AUTHENTICATED API]:
    Retrieves public configuration and connect session info to launch the Mono Connect widget on the frontend.
    """
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:manage')()]

    @extend_schema(
        tags=['Treasury - Direct Bank Feed'],
        operation_id='admin_treasury_bank_feed_connect_session',
        summary='Retrieve Open Banking connect session info (Mono Connect widget)',
        description='Fetches public API keys, bank account identifier, and active connection status for the frontend connect modal.',
        responses={200: BankFeedConnectSessionOutputSerializer}
    )
    def get(self, request, bank_account_id):
        data = BankFeedService.get_connect_session_info(bank_account_id=str(bank_account_id))
        return api_success(data=data, message="Bank connect session info retrieved.")


class BankFeedExchangeTokenAdminApi(APIView):
    """
    [AUTHENTICATED API]:
    Exchanges one-time authorization code from Mono Connect widget for persistent account ID.
    """
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:manage')()]

    @extend_schema(
        tags=['Treasury - Direct Bank Feed'],
        operation_id='admin_treasury_bank_feed_exchange_token',
        summary='Exchange Open Banking authorization code (Link Bank Account)',
        description='Exchanges the one-time code returned by the Mono Connect frontend modal and establishes an active bank feed connection.',
        request=BankFeedExchangeTokenInputSerializer,
        responses={200: BankFeedConnectionOutputSerializer}
    )
    @idempotent_endpoint()
    def post(self, request, bank_account_id):
        serializer = BankFeedExchangeTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            conn = BankFeedService.exchange_and_link_account(
                bank_account_id=str(bank_account_id),
                code=data['code'],
                provider=data.get('provider')
            )
        except DjangoValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return api_success(
            data=BankFeedConnectionOutputSerializer(conn).data,
            message="Bank account successfully linked via Open Banking."
        )


class BankFeedDisconnectAdminApi(APIView):
    """
    [AUTHENTICATED API]:
    Safely disconnects and revokes bank feed integration.
    """
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:manage')()]

    @extend_schema(
        tags=['Treasury - Direct Bank Feed'],
        operation_id='admin_treasury_bank_feed_disconnect',
        summary='Disconnect bank feed connection',
        description='Unlinks the bank feed connection and stops automated background syncs.',
        request=None,
        responses={200: BankFeedConnectionOutputSerializer}
    )
    def post(self, request, bank_account_id):
        try:
            conn = BankFeedService.disconnect_feed(bank_account_id=str(bank_account_id))
        except DjangoValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return api_success(
            data=BankFeedConnectionOutputSerializer(conn).data,
            message="Bank feed successfully disconnected."
        )


class BankFeedConfigureAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:manage')()]

    @extend_schema(
        tags=['Treasury - Direct Bank Feed'],
        operation_id='admin_treasury_bank_feed_configure',
        summary='Configure direct bank feed connection (Manual / Corporate H2H API)',
        request=BankFeedConfigureInputSerializer,
        responses={200: BankFeedConnectionOutputSerializer}
    )
    def post(self, request, bank_account_id):
        serializer = BankFeedConfigureInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        conn = BankFeedService.connection_configure(
            bank_account_id=str(bank_account_id),
            provider=data.get('provider'),
            client_id=data.get('client_id', ''),
            client_secret=data.get('client_secret', ''),
            auto_sync=data.get('auto_sync', True)
        )
        return api_success(data=BankFeedConnectionOutputSerializer(conn).data, message="Bank feed connection configured.")

    @extend_schema(
        tags=['Treasury - Direct Bank Feed'],
        operation_id='admin_treasury_bank_feed_detail',
        summary='Retrieve direct bank feed connection status',
        description='Fetches current live bank feed integration settings and provider credentials status for a bank account.',
        responses={200: BankFeedConnectionOutputSerializer}
    )
    def get(self, request, bank_account_id):
        from apps.treasury.models import BankFeedConnection
        conn = BankFeedConnection.objects.filter(bank_account_id=str(bank_account_id)).first()
        if not conn:
            return api_success(data=None, message="No direct bank feed configured.")
        return api_success(data=BankFeedConnectionOutputSerializer(conn).data)


class BankFeedSyncAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:reconcile')()]

    @extend_schema(
        tags=['Treasury - Direct Bank Feed'],
        operation_id='admin_treasury_bank_feed_sync',
        summary='Trigger live bank feed transaction sync (Mono / FNB / Open Banking)',
        request=BankFeedSyncInputSerializer,
        responses={200: BankFeedSyncOutputSerializer}
    )
    @idempotent_endpoint()
    def post(self, request, bank_account_id):
        serializer = BankFeedSyncInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            res = BankFeedService.sync_live_feed(
                bank_account_id=str(bank_account_id),
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                user=request.user
            )
        except DjangoValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return api_success(data=res, message="Live bank feed sync executed successfully.")


