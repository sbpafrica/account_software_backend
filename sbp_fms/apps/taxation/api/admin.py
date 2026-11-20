from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter

from django.http import HttpResponse
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.taxation.selectors import tax_rule_list, tax_rule_detail
from apps.taxation.services import TaxationService
from apps.taxation.serializers import (
    TaxRuleOutputSerializer, TaxRuleCreateInputSerializer, TaxRuleUpdateInputSerializer,
    IndirectTaxCalculatorInputSerializer, IndirectTaxCalculatorOutputSerializer,
    VATReturnSummaryOutputSerializer,
    SSNITScheduleGenerateInputSerializer, SSNITScheduleOutputSerializer,
    SSNITReturnSummaryOutputSerializer
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


class SSNITReturnSummaryAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('tax:read')()]

    @extend_schema(
        tags=['Taxation - Returns'],
        operation_id='admin_taxation_ssnit_return_summary',
        summary='Retrieve Ghana SSNIT Monthly Return Summary (Act 766)',
        description='Computes statutory SSNIT pension return summary: Employee Share (5.5%), Employer Share (13.0%), Tier 1 Remittance to SSNIT (13.5%), Tier 2 Remittance to Private Trustee (5.0%), and filing deadlines.',
        parameters=[
            OpenApiParameter(name='month', description='Contribution Month (1-12)', required=False, type=int),
            OpenApiParameter(name='year', description='Contribution Year (e.g. 2026)', required=False, type=int),
        ],
        responses={
            status.HTTP_200_OK: SSNITReturnSummaryOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        month_int = int(month) if month and month.isdigit() else None
        year_int = int(year) if year and year.isdigit() else None

        org = getattr(request, 'organization', None)
        org_id = org.id if org else None

        from apps.taxation.selectors import ssnit_return_summary_get
        summary = ssnit_return_summary_get(month=month_int, year=year_int, organization_id=org_id)
        return api_success(data=summary, message="SSNIT monthly return summary retrieved successfully.")


class SSNITScheduleGenerateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('tax:read')()]

    @extend_schema(
        tags=['Taxation - Returns'],
        operation_id='admin_taxation_ssnit_schedule_generate',
        summary='Generate Itemized SSNIT Monthly Contribution Return Schedule',
        description='Calculates the complete employee schedule table for SSNIT monthly reporting with Employee 5.5%, Employer 13.0%, Tier 1 (13.5%), Tier 2 (5.0%), and statutory compliance deadlines.',
        request=SSNITScheduleGenerateInputSerializer,
        responses={
            status.HTTP_200_OK: SSNITScheduleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = SSNITScheduleGenerateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employer_name = serializer.validated_data.get('employer_name')
        if not employer_name:
            org = getattr(request, 'organization', None)
            employer_name = org.name if org else "Employer Organization"

        employer_ssnit = serializer.validated_data.get('employer_ssnit_number')
        if not employer_ssnit:
            employer_ssnit = "SSNIT-GH-EMPLOYER"

        from apps.taxation.engines import GhanaTaxEngine
        schedule = GhanaTaxEngine.generate_ssnit_monthly_schedule(
            employer_name=employer_name,
            employer_ssnit_id=employer_ssnit,
            month=serializer.validated_data['month'],
            year=serializer.validated_data['year'],
            employees=serializer.validated_data['employees']
        )
        return api_success(data=schedule, message="SSNIT monthly contribution schedule generated successfully.")


class SSNITReportExportAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('tax:read')()]

    @extend_schema(
        tags=['Taxation - Returns'],
        operation_id='admin_taxation_ssnit_report_export',
        summary='Export SSNIT Monthly Contribution Return as Downloadable CSV',
        description='Generates an official formatted CSV document ready for submission to the SSNIT Employer Portal or designated bank under National Pensions Act 766.',
        request=SSNITScheduleGenerateInputSerializer,
        responses={
            status.HTTP_200_OK: str,
            status.HTTP_400_BAD_REQUEST: dict
        }
    )
    def post(self, request):
        serializer = SSNITScheduleGenerateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employer_name = serializer.validated_data.get('employer_name')
        if not employer_name:
            org = getattr(request, 'organization', None)
            employer_name = org.name if org else "Employer Organization"

        employer_ssnit = serializer.validated_data.get('employer_ssnit_number')
        if not employer_ssnit:
            employer_ssnit = "SSNIT-GH-EMPLOYER"

        from apps.taxation.engines import GhanaTaxEngine
        schedule_data = GhanaTaxEngine.generate_ssnit_monthly_schedule(
            employer_name=employer_name,
            employer_ssnit_id=employer_ssnit,
            month=serializer.validated_data['month'],
            year=serializer.validated_data['year'],
            employees=serializer.validated_data['employees']
        )

        csv_content = GhanaTaxEngine.export_ssnit_schedule_csv(schedule_data)
        filename = f"ssnit_monthly_return_{schedule_data['period_month']}_{schedule_data['period_year']}.csv"

        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

