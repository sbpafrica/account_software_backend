from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.taxation.selectors import tax_rule_list, tax_rule_detail
from apps.taxation.services import TaxationService
from apps.taxation.serializers import (
    TaxRuleOutputSerializer, TaxRuleCreateInputSerializer, TaxRuleUpdateInputSerializer,
    IndirectTaxCalculatorInputSerializer, IndirectTaxCalculatorOutputSerializer,
    VATReturnSummaryOutputSerializer
)


class TaxRuleListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('tax:read')(), CountryScopedAccess]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Taxation - Rules Admin'],
        operation_id='admin_tax_rule_list',
        summary='List multi-country statutory tax rules',
        description='Returns statutory tax rules and progressive brackets for PAYE, SSNIT, and WHT.',
        parameters=[
            OpenApiParameter(name='country', description='Filter by country code (e.g. GH, CI)', required=False, type=str),
            OpenApiParameter(name='tax_type', description='Filter by tax type (PAYE, SSNIT, WHT, VAT)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: TaxRuleOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        rules = tax_rule_list(
            country_code=request.query_params.get('country'),
            tax_type=request.query_params.get('tax_type')
        )
        return paginate_queryset(rules, request, TaxRuleOutputSerializer)

    @extend_schema(
        tags=['Taxation - Rules Admin'],
        operation_id='admin_tax_rule_create',
        summary='Create statutory tax rule',
        description='Creates a new statutory tax rule or bracket.',
        request=TaxRuleCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: TaxRuleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('tax:write') and not request.user.is_superuser:
            raise exceptions.PermissionDenied('Permission denied: tax:write or Superuser required')
        serializer = TaxRuleCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rule = TaxationService.tax_rule_create(**serializer.validated_data)
            return api_success(
                data=TaxRuleOutputSerializer(rule).data,
                message="Tax rule created successfully",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class TaxRuleDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('tax:read')()]

    @extend_schema(
        tags=['Taxation - Rules Admin'],
        operation_id='admin_tax_rule_detail',
        summary='Retrieve statutory tax rule',
        responses={
            status.HTTP_200_OK: TaxRuleOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, rule_id):
        rule = tax_rule_detail(rule_id=rule_id)
        return api_success(
            data=TaxRuleOutputSerializer(rule).data,
            message="Tax rule retrieved successfully"
        )

    @extend_schema(
        tags=['Taxation - Rules Admin'],
        operation_id='admin_tax_rule_update',
        summary='Update statutory tax rule',
        request=TaxRuleUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: TaxRuleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, rule_id):
        if not request.user.has_permission_code('tax:write') and not request.user.is_superuser:
            raise exceptions.PermissionDenied('Permission denied: tax:write or Superuser required')
        serializer = TaxRuleUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rule = TaxationService.tax_rule_update(rule_id=rule_id, **serializer.validated_data)
            return api_success(
                data=TaxRuleOutputSerializer(rule).data,
                message="Tax rule updated successfully"
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Taxation - Rules Admin'],
        operation_id='admin_tax_rule_partial_update',
        summary='Partially update statutory tax rule',
        request=TaxRuleUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: TaxRuleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, rule_id):
        return self.put(request, rule_id)

    @extend_schema(
        tags=['Taxation - Rules Admin'],
        operation_id='admin_tax_rule_delete',
        summary='Delete statutory tax rule',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, rule_id):
        if not request.user.has_permission_code('tax:write') and not request.user.is_superuser:
            raise exceptions.PermissionDenied('Permission denied: tax:write or Superuser required')
        try:
            TaxationService.tax_rule_delete(rule_id=rule_id)
            return api_success(message="Tax rule deleted successfully", status_code=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class VATReturnSummaryAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('tax:read')()]

    @extend_schema(
        tags=['Taxation - Returns'],
        operation_id='admin_taxation_vat_return_summary',
        summary='Retrieve Ghana GRA VAT & Statutory Levies Return Summary',
        description='Generate comprehensive VAT and statutory levies (NHIL, GETFund, COVID-19) return statement with input/output tax netting and withholding tax.',
        parameters=[
            OpenApiParameter(name='start_date', description='Start Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='end_date', description='End Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='country', description='Country code (default: GH)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: VATReturnSummaryOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        from datetime import datetime
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        country = request.query_params.get('country', 'GH')

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        from apps.taxation.selectors import vat_return_summary_get
        summary = vat_return_summary_get(start_date=start_date, end_date=end_date, country_code=country)
        return api_success(data=summary, message="VAT return summary retrieved successfully.")


class IndirectTaxCalculatorAdminApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Taxation - Calculator'],
        operation_id='admin_taxation_indirect_tax_calculate',
        summary='Calculate Ghana VAT, NHIL, GETFund, and COVID levies for an invoice amount',
        description='Computes statutory levies (NHIL 2.5%, GETFund 2.5%, COVID-19 Levy 1%) and standard VAT (15% on levied base) for a supplied taxable value.',
        request=IndirectTaxCalculatorInputSerializer,
        responses={
            status.HTTP_200_OK: IndirectTaxCalculatorOutputSerializer
        }
    )
    def post(self, request):
        from apps.taxation.engines import GhanaTaxEngine
        taxable_value = request.data.get('taxable_value')
        if taxable_value is None:
            raise exceptions.ValidationError({'detail': 'taxable_value is required.'})
        include_covid = request.data.get('include_covid_levy', True)
        result = GhanaTaxEngine.calculate_ghana_indirect_tax(
            taxable_value=taxable_value,
            include_covid_levy=include_covid
        )
        return api_success(data=result, message="Indirect tax calculated successfully.")

