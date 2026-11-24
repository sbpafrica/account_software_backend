from rest_framework import serializers
from .models import AuditLog, DocumentAttachment, ImportTemplate, ImportJob, ImportEntityType


class AuditLogOutputSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source='actor_user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'


class DocumentAttachmentOutputSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)

    class Meta:
        model = DocumentAttachment
        fields = '__all__'


class DocumentAttachmentCreateInputSerializer(serializers.Serializer):
    module = serializers.CharField(max_length=50)
    resource_id = serializers.CharField(max_length=100)
    file_name = serializers.CharField(max_length=255)
    file_path = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    file_size_bytes = serializers.IntegerField(default=0, required=False)
    mime_type = serializers.CharField(max_length=100, default='application/octet-stream', required=False)
    file_hash = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')


class ImportTemplateColumnSerializer(serializers.Serializer):
    header_name = serializers.CharField(max_length=100, help_text="Header as displayed in Excel")
    field_key = serializers.CharField(max_length=100, help_text="Internal target field key")
    system_field = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    data_type = serializers.ChoiceField(choices=['string', 'number', 'date', 'boolean', 'choice'], default='string')
    choices = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    is_required = serializers.BooleanField(default=False)
    default_value = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    is_custom = serializers.BooleanField(default=False, help_text="True if this is an added custom column")


class ImportTemplateOutputSerializer(serializers.ModelSerializer):
    entity_type_display = serializers.CharField(source='get_entity_type_display', read_only=True)
    columns_count = serializers.SerializerMethodField()

    class Meta:
        model = ImportTemplate
        fields = [
            'id', 'organization', 'name', 'entity_type', 'entity_type_display',
            'description', 'columns_schema', 'columns_count', 'is_default',
            'created_at', 'updated_at'
        ]

    def get_columns_count(self, obj) -> int:
        return len(obj.columns_schema) if isinstance(obj.columns_schema, list) else 0


class ImportTemplateCreateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    entity_type = serializers.ChoiceField(choices=ImportEntityType.choices)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    columns_schema = serializers.ListField(child=serializers.DictField(), required=True)
    is_default = serializers.BooleanField(default=False, required=False)


class ImportTemplateUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    columns_schema = serializers.ListField(child=serializers.DictField(), required=False)
    is_default = serializers.BooleanField(required=False)


class ImportJobOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = '__all__'


class ImportPreviewInputSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Spreadsheet file (.xlsx, .xls, or .csv)")
    template_id = serializers.UUIDField(required=False, allow_null=True)
    entity_type = serializers.ChoiceField(choices=ImportEntityType.choices, required=False, allow_null=True)


class ImportTemplateResetDefaultInputSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=ImportEntityType.choices)


class ImportPreviewOutputSerializer(serializers.Serializer):
    job_id = serializers.CharField()
    template_id = serializers.CharField()
    template_name = serializers.CharField()
    entity_type = serializers.CharField()
    file_name = serializers.CharField()
    total_rows = serializers.IntegerField()
    valid_rows_count = serializers.IntegerField()
    error_rows_count = serializers.IntegerField()
    can_import = serializers.BooleanField()
    errors = serializers.ListField(child=serializers.DictField())
    unmapped_headers = serializers.ListField(child=serializers.CharField())
    preview_rows = serializers.ListField(child=serializers.DictField())


class ImportCommitInputSerializer(serializers.Serializer):
    job_id = serializers.UUIDField(help_text="UUID returned by preview endpoint")
    validated_rows = serializers.ListField(child=serializers.DictField(), required=False, default=list)

