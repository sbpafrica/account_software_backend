from django.db import transaction
from .models import AuditLog, DocumentAttachment


class AuditService:
    @staticmethod
    def log(*, actor_user=None, action: str, module: str,
            resource_type: str, resource_id: str, changes: dict = None,
            ip_address: str = None, user_agent: str = '') -> AuditLog:
        return AuditLog.objects.create(
            actor_user=actor_user,
            action=action.strip().upper(),
            module=module.strip().lower(),
            resource_type=resource_type.strip(),
            resource_id=str(resource_id),
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent
        )


class DocumentService:
    @staticmethod
    @transaction.atomic
    def attachment_create(*, module: str, resource_id: str, file_name: str,
                          file_path: str = '', file_size_bytes: int = 0,
                          mime_type: str = 'application/octet-stream',
                          file_hash: str = '', user=None) -> DocumentAttachment:
        return DocumentAttachment.objects.create(
            module=module.strip().lower(),
            resource_id=str(resource_id),
            file_name=file_name.strip(),
            file_path=file_path.strip(),
            file_size_bytes=file_size_bytes,
            mime_type=mime_type.strip(),
            file_hash=file_hash.strip(),
            uploaded_by=user
        )

    @staticmethod
    @transaction.atomic
    def attachment_delete(*, attachment_id: str) -> None:
        doc = DocumentAttachment.objects.get(id=attachment_id)
        doc.delete()
