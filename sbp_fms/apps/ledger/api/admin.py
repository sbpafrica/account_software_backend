from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.ledger.selectors import (
    account_list, account_detail, journal_entry_list,
    journal_entry_detail, trial_balance_get
)
from apps.ledger.services import LedgerService
from apps.ledger.serializers import (
    AccountOutputSerializer, AccountCreateInputSerializer, AccountUpdateInputSerializer,
    JournalEntryOutputSerializer, JournalEntryCreateInputSerializer,
    JournalEntryReverseInputSerializer, TrialBalanceOutputSerializer
)
from apps.ledger.models import Account


class AccountListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')(), CountryScopedAccess]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Ledger - Accounts Admin'],
        operation_id='admin_ledger_account_list',
        summary='List general ledger accounts',
        description='Returns list of Chart of Accounts with filters for country and account type.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code (e.g. GH, CI)', required=False, type=str),
            OpenApiParameter(name='type', description='Account type filter (e.g. ASSET, LIABILITY)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: AccountOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        country = request.query_params.get('country')
        acct_type = request.query_params.get('type')
        accounts = account_list(country_code=country, account_type=acct_type, is_active=None)
        return paginate_queryset(accounts, request, AccountOutputSerializer)


class AccountCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')(), CountryScopedAccess]

    @extend_schema(
        tags=['Ledger - Accounts Admin'],
        operation_id='admin_ledger_account_create',
        summary='Create new general ledger account',
        description='Creates a new Account in the Chart of Accounts.',
        request=AccountCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: AccountOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = AccountCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = LedgerService.account_create(**serializer.validated_data)
        return api_success(
            data=AccountOutputSerializer(account).data,
            message="General ledger account created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class AccountDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')(), CountryScopedAccess]

    @extend_schema(
        tags=['Ledger - Accounts Admin'],
        operation_id='admin_ledger_account_detail',
        summary='Retrieve account details',
        responses={
            status.HTTP_200_OK: AccountOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, account_id):
        account = account_detail(account_id=account_id)
        return api_success(data=AccountOutputSerializer(account).data, message="Account retrieved successfully.")

    @extend_schema(
        tags=['Ledger - Accounts Admin'],
        operation_id='admin_ledger_account_update',
        summary='Update account details',
        request=AccountUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: AccountOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, account_id):
        if not request.user.has_permission_code('ledger:write'):
            return Response({'detail': 'Permission denied: ledger:write required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AccountUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = LedgerService.account_update(account_id=account_id, **serializer.validated_data)
        return api_success(data=AccountOutputSerializer(account).data, message="Account updated successfully.")

    @extend_schema(
        tags=['Ledger - Accounts Admin'],
        operation_id='admin_ledger_account_partial_update',
        summary='Partially update account details',
        request=AccountUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: AccountOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, account_id):
        return self.put(request, account_id)

    @extend_schema(
        tags=['Ledger - Accounts Admin'],
        operation_id='admin_ledger_account_delete',
        summary='Delete account',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, account_id):
        if not request.user.has_permission_code('ledger:write'):
            return Response({'detail': 'Permission denied: ledger:write required'}, status=status.HTTP_403_FORBIDDEN)
        LedgerService.account_delete(account_id=account_id)
        return api_success(message="Account deleted successfully.", status_code=status.HTTP_200_OK)


class JournalEntryListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Ledger - Journal Entries Admin'],
        operation_id='admin_ledger_journal_entry_list',
        summary='List journal entries',
        description='Returns journal entries with optional status and source module filtering.',
        parameters=[
            OpenApiParameter(name='status', description='Filter by journal status (DRAFT, POSTED, REVERSED)', required=False, type=str),
            OpenApiParameter(name='module', description='Filter by source module (e.g. PAYROLL, REVERSAL)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: JournalEntryOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        entries = journal_entry_list(
            status=request.query_params.get('status'),
            source_module=request.query_params.get('module')
        )
        return paginate_queryset(entries, request, JournalEntryOutputSerializer)


class JournalEntryDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Journal Entries Admin'],
        operation_id='admin_ledger_journal_entry_detail',
        summary='Retrieve journal entry',
        responses={
            status.HTTP_200_OK: JournalEntryOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, entry_id):
        entry = journal_entry_detail(entry_id=entry_id)
        return api_success(data=JournalEntryOutputSerializer(entry).data, message="Journal entry retrieved successfully.")

    @extend_schema(
        tags=['Ledger - Journal Entries Admin'],
        operation_id='admin_ledger_journal_entry_delete',
        summary='Delete draft journal entry',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, entry_id):
        if not request.user.has_permission_code('ledger:write'):
            return Response({'detail': 'Permission denied: ledger:write required'}, status=status.HTTP_403_FORBIDDEN)
        LedgerService.journal_entry_delete(entry_id=entry_id)
        return api_success(message="Journal entry deleted successfully.", status_code=status.HTTP_200_OK)


class JournalEntryPostAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')()]

    @extend_schema(
        tags=['Ledger - Journal Entries Admin'],
        operation_id='admin_ledger_journal_entry_post',
        summary='Post balanced journal entry',
        description='Atomically creates and posts double-entry journal lines, verifying sum(debits) == sum(credits).',
        request=JournalEntryCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: JournalEntryOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = JournalEntryCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lines_data = []
        for line in data['lines']:
            account = Account.objects.get(id=line['account_id'])
            lines_data.append({
                'account': account,
                'debit': line['debit'],
                'credit': line['credit'],
                'client_id': line.get('client_id'),
                'cost_centre': line.get('cost_centre'),
                'country_code': line.get('country_code', 'GH'),
            })

        entry = LedgerService.post_journal_entry(
            entry_number=data['entry_number'],
            posting_date=data['posting_date'],
            description=data['description'],
            source_module=data['source_module'],
            source_ref=data['source_reference_id'],
            user=request.user,
            lines_data=lines_data
        )
        return api_success(
            data=JournalEntryOutputSerializer(entry).data,
            message="Journal entry posted successfully.",
            status_code=status.HTTP_201_CREATED
        )


class JournalEntryReverseAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:reverse')()]

    @extend_schema(
        tags=['Ledger - Journal Entries Admin'],
        operation_id='admin_ledger_journal_entry_reverse',
        summary='Reverse posted journal entry',
        description='Generates inverse journal debit/credit lines and marks original as REVERSED.',
        request=JournalEntryReverseInputSerializer,
        responses={
            status.HTTP_201_CREATED: JournalEntryOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, entry_id):
        serializer = JournalEntryReverseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reversal = LedgerService.reverse_journal_entry(
            entry_id=entry_id,
            user=request.user,
            reason=serializer.validated_data['reason']
        )
        return api_success(
            data=JournalEntryOutputSerializer(reversal).data,
            message="Journal entry reversed successfully.",
            status_code=status.HTTP_201_CREATED
        )


class TrialBalanceAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')(), CountryScopedAccess]

    @extend_schema(
        tags=['Ledger - Reports Admin'],
        operation_id='admin_ledger_trial_balance',
        summary='Retrieve trial balance audit report',
        description='Calculates net balance across all active accounts as of a specified date, cached for performance.',
        parameters=[
            OpenApiParameter(name='date', description='As of date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='country', description='Filter by country code (e.g. GH, CI)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: TrialBalanceOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        date_str = request.query_params.get('date', timezone.now().date().isoformat())
        country = request.query_params.get('country')
        data = trial_balance_get(as_of_date=date_str, country_code=country)
        return api_success(data=data, message="Trial balance generated successfully.")

