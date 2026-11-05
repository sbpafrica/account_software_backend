from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.ledger.selectors import (
    account_list, account_detail, journal_entry_list,
    journal_entry_detail, trial_balance_get
)
from apps.ledger.services import LedgerService
from apps.ledger.serializers import (
    AccountOutputSerializer, AccountCreateInputSerializer,
    JournalEntryOutputSerializer, JournalEntryCreateInputSerializer,
    JournalEntryReverseInputSerializer
)
from apps.ledger.models import Account

class AccountListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')(), CountryScopedAccess]

    def get(self, request):
        country = request.query_params.get('country')
        acct_type = request.query_params.get('type')
        accounts = account_list(country_code=country, account_type=acct_type, is_active=None)
        return Response(AccountOutputSerializer(accounts, many=True).data)

class AccountCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')(), CountryScopedAccess]

    def post(self, request):
        serializer = AccountCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = LedgerService.account_create(**serializer.validated_data)
        return Response(AccountOutputSerializer(account).data, status=status.HTTP_201_CREATED)

class JournalEntryListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    def get(self, request):
        entries = journal_entry_list(
            status=request.query_params.get('status'),
            source_module=request.query_params.get('module')
        )
        return Response(JournalEntryOutputSerializer(entries, many=True).data)

class JournalEntryDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    def get(self, request, entry_id):
        entry = journal_entry_detail(entry_id=entry_id)
        return Response(JournalEntryOutputSerializer(entry).data)

class JournalEntryPostAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')()]

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
        return Response(JournalEntryOutputSerializer(entry).data, status=status.HTTP_201_CREATED)

class JournalEntryReverseAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:reverse')()]

    def post(self, request, entry_id):
        serializer = JournalEntryReverseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reversal = LedgerService.reverse_journal_entry(
            entry_id=entry_id,
            user=request.user,
            reason=serializer.validated_data['reason']
        )
        return Response(JournalEntryOutputSerializer(reversal).data, status=status.HTTP_201_CREATED)

class TrialBalanceAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')(), CountryScopedAccess]

    def get(self, request):
        date_str = request.query_params.get('date', timezone.now().date().isoformat())
        country = request.query_params.get('country')
        data = trial_balance_get(as_of_date=date_str, country_code=country)
        return Response(data)
