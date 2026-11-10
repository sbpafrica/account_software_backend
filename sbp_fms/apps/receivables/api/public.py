from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.receivables.selectors import client_invoice_list
from apps.receivables.serializers import ClientInvoiceOutputSerializer


class ClientInvoiceListPublicApi(APIView):
    """[PUBLIC API]: Clients retrieve their own billing statements."""
    permission_classes = [AllowAny]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Receivables - Public'],
        operation_id='public_receivables_client_invoices',
        summary='Retrieve client billing invoices',
        description='Returns client billing statements for self-service portal lookup.',
        responses={
            status.HTTP_200_OK: ClientInvoiceOutputSerializer(many=True),
        }
    )
    def get(self, request, client_id):
        invoices = client_invoice_list(client_id=client_id)
        return paginate_queryset(invoices, request, ClientInvoiceOutputSerializer)

