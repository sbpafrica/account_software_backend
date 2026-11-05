from rest_framework.views import APIView
from rest_framework.response import Response
from apps.payroll_escrow.selectors import client_escrow_balance_get

class ClientEscrowBalancePublicApi(APIView):
    """[PUBLIC API]: Clients check their available escrow deposit balance."""
    def get(self, request, client_id):
        country = request.query_params.get('country', 'GH')
        balance = client_escrow_balance_get(client_id=client_id, country_code=country)
        return Response({'client_id': str(client_id), 'available_escrow_balance': balance})
