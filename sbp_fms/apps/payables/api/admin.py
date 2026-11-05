from rest_framework.views import APIView
from rest_framework.response import Response
from apps.payables.selectors import supplier_list, supplier_invoice_list, supplier_invoice_detail
from apps.payables.services import PayablesService
from apps.payables.serializers import SupplierOutputSerializer, SupplierInvoiceOutputSerializer

class SupplierListAdminApi(APIView):
    def get(self, request):
        suppliers = supplier_list(country_code=request.query_params.get('country'))
        return Response(SupplierOutputSerializer(suppliers, many=True).data)

class SupplierInvoiceListAdminApi(APIView):
    def get(self, request):
        invoices = supplier_invoice_list(match_status=request.query_params.get('match_status'))
        return Response(SupplierInvoiceOutputSerializer(invoices, many=True).data)

class SupplierInvoiceDetailAdminApi(APIView):
    def get(self, request, invoice_id):
        invoice = supplier_invoice_detail(invoice_id=invoice_id)
        return Response(SupplierInvoiceOutputSerializer(invoice).data)

class ThreeWayMatchRunAdminApi(APIView):
    def post(self, request, invoice_id):
        success, message = PayablesService.execute_three_way_match(invoice_id=invoice_id)
        return Response({'success': success, 'message': message})
