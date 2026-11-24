import logging
from django.http import HttpResponse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.views import APIView
from rest_framework import status, exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.models import ImportTemplate, ImportJob, ImportEntityType
from apps.common.imports.services import ImportService
from apps.common.imports.defaults import DEFAULT_IMPORT_SCHEMAS
from apps.common.serializers import (
    ImportTemplateOutputSerializer,
    ImportTemplateCreateInputSerializer,
    ImportTemplateUpdateInputSerializer,
    ImportJobOutputSerializer,
    ImportPreviewOutputSerializer,
    ImportCommitInputSerializer,
    ImportPreviewInputSerializer,
    ImportTemplateResetDefaultInputSerializer
)

logger = logging.getLogger(__name__)


class ImportTemplateListCreateApi(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_list',
        summary='List customizable Excel import templates',
        parameters=[
            OpenApiParameter(name='entity_type', description='Filter by entity type (e.g. CHART_OF_ACCOUNTS, FIXED_ASSET, CLIENT, SUPPLIER)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer(many=True)}
    )
    def get(self, request):
        org = getattr(request, 'organization', None)
        entity_type = request.query_params.get('entity_type')

        qs = ImportTemplate.objects.all()
        if org:
            qs = qs.filter(organization=org)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)

        # Ensure default templates exist if none found
        if not qs.exists() and entity_type in ImportEntityType.values:
            ImportService.get_or_create_default_template(organization=org, entity_type=entity_type)
            qs = ImportTemplate.objects.filter(organization=org, entity_type=entity_type) if org else ImportTemplate.objects.filter(entity_type=entity_type)

        return paginate_queryset(qs, request, ImportTemplateOutputSerializer)

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_create',
        summary='Create or customize a new Excel import template',
        description='Allows clients to set up custom column names, add custom columns, delete optional columns, and configure defaults.',
        request=ImportTemplateCreateInputSerializer,
        responses={status.HTTP_201_CREATED: ImportTemplateOutputSerializer}
    )
    def post(self, request):
        serializer = ImportTemplateCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = getattr(request, 'organization', None)

        try:
            template = ImportService.template_create(
                organization=org,
                user=request.user,
                **serializer.validated_data
            )
            return api_success(
                data=ImportTemplateOutputSerializer(template).data,
                message=f"Import template '{template.name}' created successfully.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class ImportTemplateDetailApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_detail',
        summary='Retrieve template column mapping specifications',
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer}
    )
    def get(self, request, template_id):
        org = getattr(request, 'organization', None)
        qs = ImportTemplate.objects.all()
        if org:
            qs = qs.filter(organization=org)
        template = qs.filter(id=template_id).first()
        if not template:
            raise exceptions.NotFound(f"Template '{template_id}' not found.")
        return api_success(data=ImportTemplateOutputSerializer(template).data)

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_update',
        summary='Update template column mappings (rename, add custom, delete columns)',
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
                message="Template updated successfully."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_delete',
        summary='Delete a custom import template',
        responses={status.HTTP_200_OK: dict}
    )
    def delete(self, request, template_id):
        org = getattr(request, 'organization', None)
        try:
            ImportService.template_delete(template_id=template_id, organization=org)
            return api_success(message="Import template deleted successfully.")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class ImportTemplateResetDefaultApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_reset_default',
        summary='Reset template to official system standard layout',
        request=ImportTemplateResetDefaultInputSerializer,
        responses={status.HTTP_200_OK: ImportTemplateOutputSerializer}
    )
    def post(self, request):
        entity_type = request.data.get('entity_type') or request.query_params.get('entity_type')
        if not entity_type or entity_type not in ImportEntityType.values:
            raise exceptions.ValidationError({'entity_type': f"Valid entity_type required ({', '.join(ImportEntityType.values)})"})
        org = getattr(request, 'organization', None)

        template = ImportService.template_reset_default(organization=org, entity_type=entity_type)
        return api_success(
            data=ImportTemplateOutputSerializer(template).data,
            message=f"Template for '{entity_type}' reset to standard system layout."
        )


class ImportTemplateDownloadApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_template_download',
        summary='Download customized Excel template (.xlsx) with sample row',
        parameters=[
            OpenApiParameter(name='template_id', description='Template UUID (optional)', required=False, type=str),
            OpenApiParameter(name='entity_type', description='Entity type (e.g. FIXED_ASSET, CHART_OF_ACCOUNTS)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: OpenApiResponse(description="Binary Excel spreadsheet (.xlsx)")
        }
    )
    def get(self, request):
        template_id = request.query_params.get('template_id')
        entity_type = request.query_params.get('entity_type')
        org = getattr(request, 'organization', None)

        try:
            buffer, template = ImportService.download_template_workbook(
                template_id=template_id,
                entity_type=entity_type,
                organization=org
            )
            safe_name = f"{template.entity_type.lower()}_template.xlsx"
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
            return response
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class ImportPreviewApi(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_preview',
        summary='Upload Excel/CSV file and preview validation (Dry Run)',
        description='Parses uploaded file against the template column configuration. Performs schema and foreign-key checks without database mutation. Returns valid rows, error diagnostics, and unmapped headers.',
        request=ImportPreviewInputSerializer,
        responses={status.HTTP_200_OK: ImportPreviewOutputSerializer}
    )
    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise exceptions.ValidationError({'file': "Spreadsheet file (.xlsx or .csv) is required."})

        template_id = request.data.get('template_id')
        entity_type = request.data.get('entity_type')
        org = getattr(request, 'organization', None)

        try:
            preview_result = ImportService.preview_import_file(
                organization=org,
                user=request.user,
                file_obj=file_obj,
                template_id=template_id,
                entity_type=entity_type
            )
            return api_success(
                data=preview_result,
                message="File preview and validation completed."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})
        except Exception as exc:
            logger.exception("Failed to parse import preview")
            raise exceptions.ValidationError({'detail': f"Failed to parse file: {str(exc)}"})


class ImportCommitApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_commit',
        summary='Confirm and execute atomic batch import into database',
        description='Atomically imports validated rows under active tenant workspace. Flushes caches and records an audit log.',
        request=ImportCommitInputSerializer,
        responses={status.HTTP_200_OK: dict}
    )
    def post(self, request):
        serializer = ImportCommitInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = getattr(request, 'organization', None)

        try:
            result = ImportService.commit_import_job(
                job_id=serializer.validated_data['job_id'],
                organization=org,
                user=request.user,
                validated_rows=serializer.validated_data.get('validated_rows')
            )
            return api_success(data=result, message=result['message'])
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class ImportJobListApi(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Imports & Excel Migration'],
        operation_id='imports_job_list',
        summary='List past import jobs and batch migration history',
        parameters=[
            OpenApiParameter(name='entity_type', description='Filter by entity type', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: ImportJobOutputSerializer(many=True)}
    )
    def get(self, request):
        org = getattr(request, 'organization', None)
        entity_type = request.query_params.get('entity_type')

        qs = ImportJob.objects.all()
        if org:
            qs = qs.filter(organization=org)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)

        return paginate_queryset(qs, request, ImportJobOutputSerializer)
