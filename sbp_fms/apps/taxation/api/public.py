from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from apps.common.responses import api_success
from apps.taxation.services import TaxationService
from apps.taxation.serializers import TaxCalculationInputSerializer, TaxCalculationOutputSerializer


class TaxCalculatorPublicApi(APIView):
    """[PUBLIC API]: Salary tax breakdown calculator for employees and clients."""
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Taxation - Public'],
        operation_id='public_taxation_calculate',
        summary='Calculate statutory salary taxes',
        description='Computes mandatory social security and pension deductions (e.g. Ghana SSNIT Tier 1 & Tier 2).',
        request=TaxCalculationInputSerializer,
        responses={
            status.HTTP_200_OK: TaxCalculationOutputSerializer
        }
    )
    def post(self, request):
        serializer = TaxCalculationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = TaxationService.calculate_statutory_taxes(**serializer.validated_data)
        return api_success(
            data=res,
            message="Statutory tax calculation completed successfully"
        )
