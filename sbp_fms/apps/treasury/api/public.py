from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from apps.common.responses import api_success
from apps.treasury.serializers import BankWebhookInputSerializer, BankWebhookOutputSerializer


class BankWebhookPublicApi(APIView):
    """[PUBLIC API]: Endpoint for banking partner webhooks (e.g., FNB Ghana)."""
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Treasury - Public'],
        operation_id='public_treasury_bank_webhook',
        summary='Receive bank statement webhook event',
        description='Asynchronously ingests real-time banking event notifications from partner financial institutions.',
        request=BankWebhookInputSerializer,
        responses={
            status.HTTP_200_OK: BankWebhookOutputSerializer
        }
    )
    def post(self, request):
        return api_success(data={'status': 'RECEIVED'}, message="Bank statement webhook event acknowledged.")

