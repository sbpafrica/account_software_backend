from rest_framework.views import APIView
from rest_framework.response import Response
from apps.ledger.selectors import account_list
from apps.ledger.serializers import AccountOutputSerializer

class AccountListPublicApi(APIView):
    """
    [PUBLIC API]: Read-only active chart of accounts list for dropdowns and external integrations.
    """
    def get(self, request):
        country = request.query_params.get('country')
        accounts = account_list(country_code=country, is_active=True)
        return Response(AccountOutputSerializer(accounts, many=True).data)
