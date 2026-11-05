from rest_framework.views import APIView
from rest_framework.response import Response
from apps.payables.selectors import supplier_invoice_detail
from apps.payables.serializers import SupplierInvoiceOutputSerializer

class SupplierInvoiceStatusPublicApi(APIView):
    """[PUBLIC API]: Vendors check payment status of their submitted bill."""
    def get(self, request, invoice_id):
        invoice = supplier_invoice_detail(invoice_id=invoice_id)
        return Response({
            'invoice_number': invoice.invoice_number,
            'match_status': invoice.match_status,
            'net_payable_amount': invoice.net_payable_amount
        })
