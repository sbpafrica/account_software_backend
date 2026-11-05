from rest_framework.views import APIView
from rest_framework.response import Response

class BankWebhookPublicApi(APIView):
    """[PUBLIC API]: Endpoint for banking partner webhooks (e.g., FNB Ghana)."""
    def post(self, request):
        # Acknowledges bank notification
        return Response({'status': 'RECEIVED'})
