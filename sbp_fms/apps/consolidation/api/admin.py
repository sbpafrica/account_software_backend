from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode
from apps.consolidation.selectors import (
    exchange_rate_list, fx_revaluation_run_list, consolidated_trial_balance_get
)
from apps.consolidation.services import ConsolidationService
from apps.consolidation.serializers import (
    ExchangeRateInputSerializer, ExchangeRateOutputSerializer,
    LiveExchangeRateOutputSerializer,
    FXRevaluationRunInputSerializer, FXRevaluationRunOutputSerializer,
    ConsolidatedTrialBalanceOutputSerializer
)


class ExchangeRateListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Consolidation - Multi-Currency'],
        summary='List exchange rates',
        parameters=[
            OpenApiParameter('from_currency', str, required=False),
            OpenApiParameter('to_currency', str, required=False),
            OpenApiParameter('rate_date', str, required=False),
        ],
        responses={200: ExchangeRateOutputSerializer(many=True)}
    )
    def get(self, request):
        rates = exchange_rate_list(
            from_currency=request.query_params.get('from_currency'),
            to_currency=request.query_params.get('to_currency'),
            rate_date=request.query_params.get('rate_date')
        )
        return paginate_queryset(rates, request, ExchangeRateOutputSerializer)

    @extend_schema(
        tags=['Consolidation - Multi-Currency'],
        summary='Upsert exchange rate',
        request=ExchangeRateInputSerializer,
        responses={201: ExchangeRateOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('treasury:manage'):
            return Response({'detail': 'Permission denied: treasury:manage required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ExchangeRateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        rate_obj = ConsolidationService.exchange_rate_create(
            from_currency=data['from_currency'],
            to_currency=data.get('to_currency', 'GHS'),
            rate_date=data['rate_date'],
            rate=data['rate'],
            rate_type=data.get('rate_type', 'CLOSING')
        )
        return api_success(data=ExchangeRateOutputSerializer(rate_obj).data, message="Exchange rate saved.", status_code=status.HTTP_201_CREATED)


class ExchangeRateLiveAdminApi(APIView):
    """
    [AUTHENTICATED API]:
    Fetches real-time spot foreign exchange rates from Groq AI (referencing xe.com / interbank markets).
    Results are cached for a few minutes to prevent redundant queries and network latency.
    """
    permission_classes = [IsAuthenticated, HasPermissionCode('treasury:read')()]

    @extend_schema(
        tags=['Consolidation - Multi-Currency'],
        operation_id='consolidation_exchange_rate_live',
        summary='Fetch live spot exchange rate (Groq AI / XE.com)',
        description=(
            'Fetches live market exchange rate using Groq AI. '
            'Caches rates for several minutes with automated invalidation. '
            'Can pass force_refresh=true to invalidate and fetch fresh rates.'
        ),
        parameters=[
            OpenApiParameter('from_currency', str, required=False, default='USD'),
            OpenApiParameter('to_currency', str, required=False, default='GHS'),
            OpenApiParameter('force_refresh', bool, required=False, default=False),
        ],
        responses={200: LiveExchangeRateOutputSerializer}
    )
    def get(self, request):
        from_curr = request.query_params.get('from_currency', 'USD').strip().upper()
        to_curr = request.query_params.get('to_currency', 'GHS').strip().upper()
        force_refresh = str(request.query_params.get('force_refresh', 'false')).lower() in ('true', '1', 'yes')

        from apps.consolidation.groq_fx import GroqExchangeRateService
        live_data = GroqExchangeRateService.fetch_live_rate(
            from_currency=from_curr,
            to_currency=to_curr,
            force_refresh=force_refresh
        )
        return api_success(data=live_data, message=f"Live exchange rate for {from_curr}/{to_curr} retrieved successfully.")



class FXRevaluationRunAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:post')()]

    @extend_schema(
        tags=['Consolidation - Multi-Currency'],
        summary='List FX revaluation runs',
        responses={200: FXRevaluationRunOutputSerializer(many=True)}
    )
    def get(self, request):
        runs = fx_revaluation_run_list()
        return api_success(data=FXRevaluationRunOutputSerializer(runs, many=True).data)

    @extend_schema(
        tags=['Consolidation - Multi-Currency'],
        summary='Execute FX revaluation run and post balancing GL entry',
        request=FXRevaluationRunInputSerializer,
        responses={201: FXRevaluationRunOutputSerializer}
    )
    def post(self, request):
        serializer = FXRevaluationRunInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        run = ConsolidationService.fx_revaluation_post(
            revaluation_date=data['revaluation_date'],
            reporting_currency=data.get('reporting_currency', 'GHS'),
            user=request.user,
            notes=data.get('notes', '')
        )
        return api_success(data=FXRevaluationRunOutputSerializer(run).data, message="FX revaluation completed.", status_code=status.HTTP_201_CREATED)


class ConsolidatedTrialBalanceAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Consolidation - Multi-Currency'],
        summary='Get multi-entity consolidated trial balance',
        parameters=[
            OpenApiParameter('as_of_date', str, required=False),
            OpenApiParameter('reporting_currency', str, required=False, default='GHS'),
        ],
        responses={200: ConsolidatedTrialBalanceOutputSerializer}
    )
    def get(self, request):
        as_of = request.query_params.get('as_of_date')
        rep_curr = request.query_params.get('reporting_currency', 'GHS')
        tb = consolidated_trial_balance_get(as_of_date=as_of, reporting_currency=rep_curr)
        return api_success(data=tb, message="Consolidated trial balance retrieved.")
