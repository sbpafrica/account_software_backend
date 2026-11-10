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
    TaxRuleOutputSerializer, TaxRuleCreateInputSerializer, TaxRuleUpdateInputSerializer
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
