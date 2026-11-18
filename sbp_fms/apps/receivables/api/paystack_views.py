from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.core.exceptions import ValidationError

from apps.common.responses import api_success, api_error
from apps.common.idempotency import idempotent_endpoint
from apps.common.throttling import FinancialMutationRateThrottle, SbpUserRateThrottle
from apps.receivables.services import ReceivablesService
from apps.receivables.serializers import (
    InvoicePaystackInitializeInputSerializer,
    InvoicePaystackInitializeOutputSerializer,
    InvoicePaystackVerifyInputSerializer,
    InvoicePaystackVerifyOutputSerializer,
    PaymentReceiptOutputSerializer,
    ClientInvoiceOutputSerializer,
)


class InvoicePaystackInitializeApi(APIView):
    """
    [AUTHENTICATED API]:
    Initializes a Paystack online payment checkout for an outstanding Client Invoice.
    Enforces strict idempotency ('Idempotency-Key' / 'X-Idempotency-Key' header) to avoid duplicate checkouts.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [FinancialMutationRateThrottle, SbpUserRateThrottle]

    @extend_schema(
        tags=['Accounts Receivable'],
        operation_id='receivables_invoice_paystack_initialize',
        summary='Initialize Paystack checkout for Client Invoice',
        description=(
            'Initiates an online payment checkout with Paystack for a Client Invoice. '
            'Returns the secure Paystack checkout authorization_url and reference. '
            'Protected by financial idempotency headers.'
        ),
        request=InvoicePaystackInitializeInputSerializer,
        responses={
            status.HTTP_201_CREATED: InvoicePaystackInitializeOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Invoice not in payable state or invalid amount"),
            status.HTTP_409_CONFLICT: OpenApiResponse(description="Concurrent charge operation in progress"),
        }
    )
    @idempotent_endpoint()
    def post(self, request, invoice_id):
        serializer = InvoicePaystackInitializeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data.get('amount')
        callback_url = serializer.validated_data.get('callback_url')

        try:
            invoice, paystack_data = ReceivablesService.initialize_invoice_paystack_payment(
                invoice_id=invoice_id,
                amount=amount,
                callback_url=callback_url,
                user=request.user
            )
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        payload = {
            'authorization_url': paystack_data.get('authorization_url', ''),
            'access_code': paystack_data.get('access_code', ''),
            'reference': paystack_data.get('reference', ''),
            'amount': amount or invoice.balance_due,
            'currency': 'GHS',
            'invoice_number': invoice.invoice_number,
        }
        return api_success(
            data=payload,
            message="Paystack invoice checkout initialized. Redirect user to authorization_url.",
            status_code=status.HTTP_201_CREATED
        )


class InvoicePaystackVerifyApi(APIView):
    """
    [AUTHENTICATED API]:
    Verifies Paystack payment completion for an invoice, creates the payment receipt,
    and posts double-entry GL journals atomically.
    Idempotent: Re-verifying returns the confirmed receipt safely.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Accounts Receivable'],
        operation_id='receivables_invoice_paystack_verify',
        summary='Verify Paystack payment for Client Invoice',
        description=(
            'Verifies transaction status with Paystack. Upon success, creates a PaymentReceipt, '
            'allocates payment to the invoice, updates invoice status to PAID/PARTIALLY_PAID, '
            'and creates balanced GL journal entries atomically.'
        ),
        request=InvoicePaystackVerifyInputSerializer,
        responses={
            status.HTTP_200_OK: InvoicePaystackVerifyOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Payment verification failed or invalid reference"),
            status.HTTP_409_CONFLICT: OpenApiResponse(description="Concurrent operation in progress"),
        }
    )
    @idempotent_endpoint()
    def post(self, request):
        serializer = InvoicePaystackVerifyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reference = serializer.validated_data['reference']

        try:
            receipt, invoice, success = ReceivablesService.verify_invoice_paystack_payment(
                reference=reference,
                user=request.user
            )
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        if not success:
            return api_error(message="Paystack payment verification was not successful.", status_code=status.HTTP_400_BAD_REQUEST)

        receipt_data = PaymentReceiptOutputSerializer(receipt).data if receipt else None
        invoice_data = ClientInvoiceOutputSerializer(invoice).data if invoice else None

        payload = {
            'status': 'SUCCESS',
            'message': f"Invoice {invoice.invoice_number if invoice else ''} payment verified and receipt recorded.",
            'receipt': receipt_data,
            'invoice': invoice_data,
        }
        return api_success(data=payload, message="Payment successfully verified and allocated.")
