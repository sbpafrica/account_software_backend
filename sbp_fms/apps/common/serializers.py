from rest_framework import serializers
from .models import AuditLog, DocumentAttachment


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
