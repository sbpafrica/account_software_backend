from rest_framework.views import APIView
from rest_framework.response import Response
from apps.taxation.services import TaxationService
from apps.taxation.serializers import TaxCalculationInputSerializer

class TaxCalculatorPublicApi(APIView):
    """[PUBLIC API]: Salary tax breakdown calculator for employees and clients."""
    def post(self, request):
        serializer = TaxCalculationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = TaxationService.calculate_statutory_taxes(**serializer.validated_data)
        return Response(res)
