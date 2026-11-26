import logging
from django.http import HttpResponse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, exceptions, serializers
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.models import ImportTemplate, ImportEntityType
from apps.common.imports.services import ImportService
from apps.common.imports.defaults import get_default_schema_for_entity
from apps.common.serializers import (
    ImportTemplateOutputSerializer,
    ImportTemplateCreateInputSerializer,
    ImportTemplateUpdateInputSerializer,
    ImportPreviewOutputSerializer,
    ImportCommitInputSerializer,
    ImportPreviewInputSerializer,
)
from apps.invoicing.api.admin import BaseInvoicingAdminApi
from apps.invoicing.selectors import InvoicingSelector
from apps.invoicing.excel import generate_invoices_excel_export

logger = logging.getLogger(__name__)


class InvoiceExcelTemplateCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    columns_schema = ImportTemplateCreateInputSerializer().fields['columns_schema']
    is_default = serializers.BooleanField(default=False)


class InvoiceExcelTemplateListCreateApi(BaseInvoicingAdminApi):
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_list',
        summary='List invoice Excel header templates',
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer(many=True)}
    )
    def get(self, request):
        org = getattr(request, 'organization', None)
        qs = ImportTemplate.objects.filter(entity_type=ImportEntityType.INVOICE)
        if org:
            qs = qs.filter(organization=org)
        if not qs.exists():
            ImportService.get_or_create_default_template(organization=org, entity_type=ImportEntityType.INVOICE)
            qs = ImportTemplate.objects.filter(entity_type=ImportEntityType.INVOICE)
            if org:
                qs = qs.filter(organization=org)
        return paginate_queryset(qs, request, ImportTemplateOutputSerializer)

    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_create',
        summary='Create custom Excel header setup for invoices',
        description='Allows users to customize Excel column headers, add custom columns, remove optional columns, and reorder columns for invoice import/export.',
        request=InvoiceExcelTemplateCreateSerializer,
        responses={status.HTTP_201_CREATED: ImportTemplateOutputSerializer}
    )
    def post(self, request):
        serializer = InvoiceExcelTemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = getattr(request, 'organization', None)
        try:
            template = ImportService.template_create(
                organization=org,
                user=request.user,
                entity_type=ImportEntityType.INVOICE,
                **serializer.validated_data
            )
            return api_success(
                data=ImportTemplateOutputSerializer(template).data,
                message=f"Invoice Excel template '{template.name}' created successfully.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class InvoiceExcelTemplateDetailApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_detail',
        summary='Retrieve invoice Excel header template',
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer}
    )
    def get(self, request, template_id):
        org = getattr(request, 'organization', None)
        qs = ImportTemplate.objects.filter(entity_type=ImportEntityType.INVOICE)
        if org:
            qs = qs.filter(organization=org)
        template = qs.filter(id=template_id).first()
        if not template:
            raise exceptions.NotFound(f"Invoice Excel template '{template_id}' not found.")
        return api_success(data=ImportTemplateOutputSerializer(template).data)

    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_update',
        summary='Update invoice Excel header setup (rename, add, delete, reorder columns)',
        request=ImportTemplateUpdateInputSerializer,
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer}
    )
    def put(self, request, template_id):
        serializer = ImportTemplateUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = getattr(request, 'organization', None)
        try:
            template = ImportService.template_update(
                template_id=template_id,
                organization=org,
                **serializer.validated_data
            )
            return api_success(
                data=ImportTemplateOutputSerializer(template).data,
                message="Invoice Excel template updated successfully."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_delete',
        summary='Delete custom invoice Excel template',
        responses={status.HTTP_200_OK: dict}
    )
    def delete(self, request, template_id):
        org = getattr(request, 'organization', None)
        try:
            ImportService.template_delete(template_id=template_id, organization=org)
            return api_success(message="Invoice Excel template deleted successfully.")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class InvoiceExcelTemplateResetDefaultApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_reset',
        summary='Reset invoice Excel headers to system default',
        request=None,
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer}
    )
    def post(self, request):
        org = getattr(request, 'organization', None)
        template = ImportService.template_reset_to_default(
            organization=org,
            entity_type=ImportEntityType.INVOICE,
            user=request.user
        )
        return api_success(
            data=ImportTemplateOutputSerializer(template).data,
            message="Invoice Excel template reset to system defaults."
        )


class InvoiceExcelTemplateDownloadApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_template_download',
        summary='Download customized Excel (.xlsx) template for uploading invoices',
        parameters=[
            OpenApiParameter(name='template_id', description='Optional custom ImportTemplate UUID', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: bytes}
    )
    def get(self, request):
        org = getattr(request, 'organization', None)
        template_id = request.query_params.get('template_id')
        try:
            buffer, template = ImportService.download_template_workbook(
                organization=org,
                entity_type=ImportEntityType.INVOICE,
                template_id=template_id
            )
            filename = f"{template.entity_type.lower()}_import_template.xlsx"
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class InvoiceExcelPreviewApi(BaseInvoicingAdminApi):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_preview',
        summary='Upload invoice Excel (.xlsx) and preview validated rows',
        request=ImportPreviewInputSerializer,
        responses={status.HTTP_200_OK: ImportPreviewOutputSerializer}
    )
    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise exceptions.ValidationError({'file': 'Please attach an Excel (.xlsx) file.'})

        template_id = request.data.get('template_id')
        org = getattr(request, 'organization', None)
        try:
            result = ImportService.preview_import_file(
                organization=org,
                user=request.user,
                file_obj=file_obj,
                entity_type=ImportEntityType.INVOICE,
                template_id=template_id
            )
            return api_success(
                data=result,
                message="Invoice Excel preview completed. Review validation summary before committing."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class InvoiceExcelCommitApi(BaseInvoicingAdminApi):
    parser_classes = [JSONParser]

    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_commit',
        summary='Commit previewed invoice Excel upload into database',
        request=ImportCommitInputSerializer,
        responses={status.HTTP_201_CREATED: dict}
    )
    def post(self, request):
        serializer = ImportCommitInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = getattr(request, 'organization', None)
        try:
            result = ImportService.commit_import_job(
                organization=org,
                user=request.user,
                job_id=serializer.validated_data['job_id'],
                validated_rows=serializer.validated_data['validated_rows']
            )
            return api_success(
                data=result,
                message=result["message"],
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class InvoiceExcelExportApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Excel Import & Export'],
        operation_id='invoicing_excel_export',
        summary='Download existing invoices as Excel (.xlsx) using custom headers',
        description='Exports invoices matching the optional filters into an .xlsx workbook formatted according to the specified or default INVOICE Excel template.',
        parameters=[
            OpenApiParameter(name='template_id', description='Optional custom ImportTemplate UUID to control Excel headers & column order', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by invoice status', required=False, type=str),
            OpenApiParameter(name='invoice_type', description='Filter by invoice type', required=False, type=str),
            OpenApiParameter(name='client_id', description='Filter by client UUID', required=False, type=str),
            OpenApiParameter(name='category_id', description='Filter by category UUID', required=False, type=str),
            OpenApiParameter(name='start_date', description='Filter issue_date >= YYYY-MM-DD', required=False, type=str),
            OpenApiParameter(name='end_date', description='Filter issue_date <= YYYY-MM-DD', required=False, type=str),
            OpenApiParameter(name='search', description='Search by invoice number, PO reference, or client', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: bytes}
    )
    def get(self, request):
        org = getattr(request, 'organization', None)
        template_id = request.query_params.get('template_id')

        template = None
        if template_id:
            qs = ImportTemplate.objects.filter(id=template_id, entity_type=ImportEntityType.INVOICE)
            if org:
                qs = qs.filter(organization=org)
            template = qs.first()
            if not template:
                raise exceptions.NotFound(f"Invoice Excel template '{template_id}' not found.")
        else:
            qs = ImportTemplate.objects.filter(entity_type=ImportEntityType.INVOICE, is_default=True)
            if org:
                qs = qs.filter(organization=org)
            template = qs.first()

        columns_schema = (
            template.columns_schema
            if template and template.columns_schema
            else get_default_schema_for_entity(ImportEntityType.INVOICE)
        )

        invoices = InvoicingSelector.invoice_list(
            status=request.query_params.get('status'),
            invoice_type=request.query_params.get('invoice_type'),
            client_id=request.query_params.get('client_id'),
            category_id=request.query_params.get('category_id'),
            start_date=request.query_params.get('start_date'),
            end_date=request.query_params.get('end_date'),
            search=request.query_params.get('search'),
        )

        buffer = generate_invoices_excel_export(invoices=invoices, columns_schema=columns_schema)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = 'attachment; filename="invoices_export.xlsx"'
        return response
