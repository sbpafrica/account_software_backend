from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.ledger.selectors import (
    account_list, account_detail, journal_entry_list,
    journal_entry_detail, trial_balance_get,
    profit_and_loss_get, balance_sheet_get,
    cash_flow_statement_get, gl_account_statement_get
)
from apps.ledger.services import LedgerService
from apps.ledger.serializers import (
    AccountOutputSerializer, AccountCreateInputSerializer, AccountUpdateInputSerializer,
    JournalEntryOutputSerializer, JournalEntryCreateInputSerializer,
    JournalEntryReverseInputSerializer, TrialBalanceOutputSerializer,
    ProfitAndLossOutputSerializer, BalanceSheetOutputSerializer,
    CashFlowStatementOutputSerializer, GLAccountStatementOutputSerializer,
    CEOExecutiveDashboardOutputSerializer
)
from apps.ledger.models import Account, Department, CostCentre


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


# ============================================================================
# COMPANY PROFILE & ACCOUNTING DIMENSIONS
# ============================================================================

from apps.ledger.models import CompanyProfile, Department, CostCentre
from apps.ledger.serializers import (
    CompanyProfileOutputSerializer, CompanyProfileUpdateInputSerializer,
    DepartmentOutputSerializer, DepartmentCreateInputSerializer,
    CostCentreOutputSerializer, CostCentreCreateInputSerializer
)


class CompanyProfileAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')()]

    @extend_schema(
        tags=['Ledger - Company Profile'],
        operation_id='admin_ledger_company_profile_get',
        summary='Retrieve company profile for country',
        description='Retrieve company profile, legal entity details, reporting currency, and tax registration for a country.',
        parameters=[OpenApiParameter(name='country', description='Two-letter country code (e.g. GH, NG, CI)', required=False, type=str)],
        responses={status.HTTP_200_OK: CompanyProfileOutputSerializer}
    )
    def get(self, request):
        country = request.query_params.get('country', 'GH')
        profile = LedgerService.company_profile_get_or_create(country_code=country)
        return api_success(data=CompanyProfileOutputSerializer(profile).data)

    @extend_schema(
        tags=['Ledger - Company Profile'],
        operation_id='admin_ledger_company_profile_update',
        summary='Update company profile for country',
        description='Update legal entity name, base currency, fiscal year end, address, or tax registration details.',
        parameters=[OpenApiParameter(name='country', description='Two-letter country code (e.g. GH, NG, CI)', required=False, type=str)],
        request=CompanyProfileUpdateInputSerializer,
        responses={status.HTTP_200_OK: CompanyProfileOutputSerializer}
    )
    def put(self, request):
        country = request.query_params.get('country', 'GH')
        serializer = CompanyProfileUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = LedgerService.company_profile_update(country_code=country, **serializer.validated_data)
        return api_success(data=CompanyProfileOutputSerializer(profile).data, message="Company profile updated successfully.")


class DepartmentListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Departments & Cost Centres'],
        operation_id='admin_ledger_department_list',
        summary='List active organizational departments',
        description='Retrieve all active departments used for financial reporting and cost allocation.',
        responses={status.HTTP_200_OK: DepartmentOutputSerializer(many=True)}
    )
    def get(self, request):
        depts = Department.objects.filter(is_active=True)
        return api_success(data=DepartmentOutputSerializer(depts, many=True).data)

    @extend_schema(
        tags=['Ledger - Departments & Cost Centres'],
        operation_id='admin_ledger_department_create',
        summary='Create new organizational department',
        description='Register a new department with unique code and name for departmental P&L tracking.',
        request=DepartmentCreateInputSerializer,
        responses={status.HTTP_201_CREATED: DepartmentOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('ledger:write'):
            return Response({'detail': 'Permission denied: ledger:write required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DepartmentCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dept = LedgerService.department_create(**serializer.validated_data)
        return api_success(data=DepartmentOutputSerializer(dept).data, message="Department created successfully.", status_code=status.HTTP_201_CREATED)


class CostCentreListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Departments & Cost Centres'],
        operation_id='admin_ledger_cost_centre_list',
        summary='List active cost centres',
        description='Retrieve all active cost centres along with their parent department associations.',
        responses={status.HTTP_200_OK: CostCentreOutputSerializer(many=True)}
    )
    def get(self, request):
        centres = CostCentre.objects.filter(is_active=True).select_related('department')
        return api_success(data=CostCentreOutputSerializer(centres, many=True).data)

    @extend_schema(
        tags=['Ledger - Departments & Cost Centres'],
        operation_id='admin_ledger_cost_centre_create',
        summary='Create new cost centre',
        description='Register a new cost centre mapped to a department for granular expense tracking.',
        request=CostCentreCreateInputSerializer,
        responses={status.HTTP_201_CREATED: CostCentreOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('ledger:write'):
            return Response({'detail': 'Permission denied: ledger:write required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = CostCentreCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        centre = LedgerService.cost_centre_create(**serializer.validated_data)
        return api_success(data=CostCentreOutputSerializer(centre).data, message="Cost centre created successfully.", status_code=status.HTTP_201_CREATED)


class ProfitAndLossAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Reports'],
        operation_id='admin_ledger_profit_and_loss',
        summary='Retrieve standard Profit and Loss Statement (Income Statement)',
        parameters=[
            OpenApiParameter(name='start_date', description='Start Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='end_date', description='End Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='cost_centre', description='Cost Centre code filter', required=False, type=str),
            OpenApiParameter(name='country', description='Country code filter (e.g. GH)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: ProfitAndLossOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        cost_centre = request.query_params.get('cost_centre')
        country = request.query_params.get('country')
        report = profit_and_loss_get(
            start_date=start_date,
            end_date=end_date,
            cost_centre=cost_centre,
            country_code=country
        )
        return api_success(data=report, message="Profit and Loss statement retrieved successfully.")


class BalanceSheetAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Reports'],
        operation_id='admin_ledger_balance_sheet',
        summary='Retrieve Balance Sheet Statement (Statement of Financial Position)',
        parameters=[
            OpenApiParameter(name='as_of_date', description='As of Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='country', description='Country code filter (e.g. GH)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: BalanceSheetOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        as_of_date = request.query_params.get('as_of_date')
        country = request.query_params.get('country')
        report = balance_sheet_get(as_of_date=as_of_date, country_code=country)
        return api_success(data=report, message="Balance sheet retrieved successfully.")


class CashFlowStatementAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Reports'],
        operation_id='admin_ledger_cash_flow_statement',
        summary='Retrieve Cash Flow Statement (Indirect Method)',
        parameters=[
            OpenApiParameter(name='start_date', description='Start Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='end_date', description='End Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='country', description='Country code filter (e.g. GH)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: CashFlowStatementOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        country = request.query_params.get('country')
        report = cash_flow_statement_get(start_date=start_date, end_date=end_date, country_code=country)
        return api_success(data=report, message="Cash flow statement retrieved successfully.")


class GLAccountStatementAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Reports'],
        operation_id='admin_ledger_gl_account_statement',
        summary='Retrieve running GL Account Statement',
        parameters=[
            OpenApiParameter(name='start_date', description='Start Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='end_date', description='End Date (YYYY-MM-DD)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: GLAccountStatementOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, account_id):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        report = gl_account_statement_get(account_id=account_id, start_date=start_date, end_date=end_date)
        return api_success(data=report, message="GL account statement retrieved successfully.")


class CEOExecutiveDashboardAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Ledger - Reports'],
        operation_id='admin_ledger_ceo_executive_dashboard',
        summary='Retrieve Executive CEO Real-Time Intelligence Dashboard',
        description='Synthesizes real-time enterprise metrics across liquidity, receivables, payables, profitability, and financial ratios.',
        parameters=[
            OpenApiParameter(name='as_of_date', description='As of Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='country', description='Country code filter (e.g. GH)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: CEOExecutiveDashboardOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        as_of = request.query_params.get('as_of_date')
        country = request.query_params.get('country')
        from apps.ledger.selectors import ceo_executive_dashboard_get
        dashboard = ceo_executive_dashboard_get(as_of_date=as_of, country_code=country)
        return api_success(data=dashboard, message="CEO Executive Dashboard generated successfully.")




