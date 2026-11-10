from rest_framework.views import APIView
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode
from apps.common.selectors import audit_log_list, document_attachment_list
from apps.common.services import DocumentService
from apps.common.serializers import (
    AuditLogOutputSerializer,
    DocumentAttachmentOutputSerializer, DocumentAttachmentCreateInputSerializer
)


class AuditLogListAdminApi(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Common - Audit Log'],
        operation_id='admin_common_audit_log_list',
        summary='Retrieve immutable system audit log records',
        parameters=[
            OpenApiParameter(name='module', description='Filter by module (e.g. ledger, payables, receivables, treasury)', required=False, type=str),
            OpenApiParameter(name='resource_type', description='Filter by resource type (e.g. JournalEntry, PaymentVoucher)', required=False, type=str),
            OpenApiParameter(name='resource_id', description='Filter by resource UUID', required=False, type=str),
            OpenApiParameter(name='action', description='Filter by action (e.g. CREATE, POST, APPROVE)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: AuditLogOutputSerializer(many=True)}
    )
    def get(self, request):
        logs = audit_log_list(
            module=request.query_params.get('module'),
            resource_type=request.query_params.get('resource_type'),
            resource_id=request.query_params.get('resource_id'),
            action=request.query_params.get('action')
        )
        return paginate_queryset(logs, request, AuditLogOutputSerializer)


class DocumentAttachmentListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Common - Document Vault'],
        operation_id='admin_common_attachment_list',
        summary='List document attachments for a record',
        parameters=[
            OpenApiParameter(name='module', description='Module name (e.g. payables, receivables)', required=False, type=str),
            OpenApiParameter(name='resource_id', description='Record UUID', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: DocumentAttachmentOutputSerializer(many=True)}
    )
    def get(self, request):
        attachments = document_attachment_list(
            module=request.query_params.get('module'),
            resource_id=request.query_params.get('resource_id')
        )
        return paginate_queryset(attachments, request, DocumentAttachmentOutputSerializer)

    @extend_schema(
        tags=['Common - Document Vault'],
        operation_id='admin_common_attachment_create',
        summary='Record uploaded document metadata',
        request=DocumentAttachmentCreateInputSerializer,
        responses={status.HTTP_201_CREATED: DocumentAttachmentOutputSerializer}
    )
    def post(self, request):
        serializer = DocumentAttachmentCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = DocumentService.attachment_create(
            user=request.user,
            **serializer.validated_data
        )
        return api_success(
            data=DocumentAttachmentOutputSerializer(doc).data,
            message="Document attachment recorded successfully.",
            status_code=status.HTTP_201_CREATED
        )


class DocumentAttachmentDeleteAdminApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Common - Document Vault'],
        operation_id='admin_common_attachment_delete',
        summary='Delete document attachment',
        responses={status.HTTP_200_OK: dict}
    )
    def delete(self, request, attachment_id):
        DocumentService.attachment_delete(attachment_id=str(attachment_id))
        return api_success(message="Document attachment deleted successfully.")
