from typing import Optional
from .models import AuditLog, DocumentAttachment


def audit_log_list(
    *,
    module: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None
) -> list[AuditLog]:
    qs = AuditLog.objects.select_related('actor_user').all()
    if module:
        qs = qs.filter(module=module.strip().lower())
    if resource_type:
        qs = qs.filter(resource_type=resource_type.strip())
    if resource_id:
        qs = qs.filter(resource_id=str(resource_id))
    if action:
        qs = qs.filter(action=action.strip().upper())
    return list(qs)


def document_attachment_list(
    *,
    module: Optional[str] = None,
    resource_id: Optional[str] = None
) -> list[DocumentAttachment]:
    qs = DocumentAttachment.objects.select_related('uploaded_by').all()
    if module:
        qs = qs.filter(module=module.strip().lower())
    if resource_id:
        qs = qs.filter(resource_id=str(resource_id))
    return list(qs)
