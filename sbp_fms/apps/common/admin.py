from django.contrib import admin
from apps.common.models import AuditLog, DocumentAttachment, IdempotencyRecord, ImportTemplate, ImportJob


@admin.register(ImportTemplate)
class ImportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'entity_type', 'organization', 'is_default', 'created_by', 'created_at')
    list_filter = ('entity_type', 'is_default')
    search_fields = ('name', 'description')


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ('entity_type', 'file_name', 'organization', 'total_rows', 'successful_rows', 'failed_rows', 'status', 'created_at')
    list_filter = ('entity_type', 'status')
    search_fields = ('file_name',)
    readonly_fields = ('organization', 'template', 'entity_type', 'file_name', 'file_size_bytes', 'total_rows', 'successful_rows', 'failed_rows', 'status', 'error_summary', 'executed_by', 'created_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'module', 'resource_type', 'resource_id', 'actor_user', 'ip_address', 'timestamp')
    list_filter = ('action', 'module', 'resource_type')
    search_fields = ('resource_type', 'resource_id', 'ip_address')
    readonly_fields = ('id', 'actor_user', 'action', 'module', 'resource_type', 'resource_id', 'ip_address', 'user_agent', 'changes', 'timestamp')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(
                actor_user__organization_memberships__organization__memberships__user=request.user
            ).distinct()
        return qs

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'module', 'resource_id', 'file_size_bytes', 'uploaded_by', 'created_at')
    list_filter = ('module',)
    search_fields = ('file_name', 'resource_id')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(
                uploaded_by__organization_memberships__organization__memberships__user=request.user
            ).distinct()
        return qs


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ('key', 'request_method', 'request_path', 'response_status_code', 'is_processing', 'created_at')
    list_filter = ('is_processing', 'request_method')
    search_fields = ('key', 'request_path')
    readonly_fields = ('key', 'user', 'organization', 'request_path', 'request_method', 'request_digest', 'response_status_code', 'response_headers', 'response_body', 'is_processing', 'expires_at', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(organization__memberships__user=request.user).distinct()
        return qs

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
