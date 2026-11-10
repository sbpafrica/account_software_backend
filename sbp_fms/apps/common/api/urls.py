from django.urls import path
from apps.common.api.admin import (
    AuditLogListAdminApi,
    DocumentAttachmentListCreateAdminApi,
    DocumentAttachmentDeleteAdminApi
)

urlpatterns = [
    # Audit Trail
    path('admin/audit-logs/', AuditLogListAdminApi.as_view(), name='audit-log-list-admin'),

    # Document Attachments Vault
    path('admin/attachments/', DocumentAttachmentListCreateAdminApi.as_view(), name='document-attachment-list-create-admin'),
    path('admin/attachments/<uuid:attachment_id>/', DocumentAttachmentDeleteAdminApi.as_view(), name='document-attachment-delete-admin'),
]
