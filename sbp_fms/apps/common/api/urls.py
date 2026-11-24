from django.urls import path
from apps.common.api.admin import (
    AuditLogListAdminApi,
    DocumentAttachmentListCreateAdminApi,
    DocumentAttachmentDeleteAdminApi
)
from apps.common.api.imports import (
    ImportTemplateListCreateApi,
    ImportTemplateDetailApi,
    ImportTemplateResetDefaultApi,
    ImportTemplateDownloadApi,
    ImportPreviewApi,
    ImportCommitApi,
    ImportJobListApi
)

urlpatterns = [
    # Audit Trail
    path('admin/audit-logs/', AuditLogListAdminApi.as_view(), name='audit-log-list-admin'),

    # Document Attachments Vault
    path('admin/attachments/', DocumentAttachmentListCreateAdminApi.as_view(), name='document-attachment-list-create-admin'),
    path('admin/attachments/<uuid:attachment_id>/', DocumentAttachmentDeleteAdminApi.as_view(), name='document-attachment-delete-admin'),

    # Customizable Excel Import Hub
    path('imports/templates/', ImportTemplateListCreateApi.as_view(), name='imports-template-list-create'),
    path('imports/templates/reset-default/', ImportTemplateResetDefaultApi.as_view(), name='imports-template-reset-default'),
    path('imports/templates/download/', ImportTemplateDownloadApi.as_view(), name='imports-template-download'),
    path('imports/templates/<uuid:template_id>/', ImportTemplateDetailApi.as_view(), name='imports-template-detail'),
    path('imports/preview/', ImportPreviewApi.as_view(), name='imports-preview'),
    path('imports/commit/', ImportCommitApi.as_view(), name='imports-commit'),
    path('imports/jobs/', ImportJobListApi.as_view(), name='imports-job-list'),
]
