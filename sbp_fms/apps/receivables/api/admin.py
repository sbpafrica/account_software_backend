from rest_framework.views import APIView
from rest_framework.response import Response
from apps.receivables.selectors import client_list, client_invoice_list, aging_report_get
from apps.receivables.serializers import ClientOutputSerializer, ClientInvoiceOutputSerializer

class ClientListAdminApi(APIView):
    def get(self, request):
        clients = client_list(country_code=request.query_params.get('country'))
        return Response(ClientOutputSerializer(clients, many=True).data)

class ClientInvoiceListAdminApi(APIView):
    def get(self, request):
        invoices = client_invoice_list(status=request.query_params.get('status'))
        return Response(ClientInvoiceOutputSerializer(invoices, many=True).data)

class AgingReportAdminApi(APIView):
    def get(self, request):
        report = aging_report_get(country_code=request.query_params.get('country'))
        return Response(report)
