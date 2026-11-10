from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from apps.common.responses import api_success
from apps.payables.selectors import supplier_invoice_detail
from apps.payables.serializers import SupplierInvoicePublicStatusOutputSerializer


class SupplierInvoiceStatusPublicApi(APIView):
    """[PUBLIC API]: Vendors check payment status of their submitted bill."""
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Payables - Public'],
        operation_id='public_payables_invoice_status',
        summary='Check supplier bill status',
        description='Vendors query matching and payment status of a submitted invoice.',
        responses={
            status.HTTP_200_OK: SupplierInvoicePublicStatusOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, invoice_id):
        invoice = supplier_invoice_detail(invoice_id=invoice_id)
        payload = {
            'invoice_number': invoice.invoice_number,
            'match_status': invoice.match_status,
            'net_payable_amount': invoice.net_payable_amount
        }
        return api_success(data=payload, message="Supplier invoice status retrieved successfully.")

