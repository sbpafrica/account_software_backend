from rest_framework.views import APIView
from rest_framework.response import Response
from apps.receivables.selectors import client_invoice_list
from apps.receivables.serializers import ClientInvoiceOutputSerializer

class ClientInvoiceListPublicApi(APIView):
    """[PUBLIC API]: Clients retrieve their own billing statements."""
    def get(self, request, client_id):
        invoices = client_invoice_list(client_id=client_id)
        return Response(ClientInvoiceOutputSerializer(invoices, many=True).data)
