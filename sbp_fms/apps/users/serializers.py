from rest_framework import serializers
from .models import User, Role, Permission


class PermissionOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'code', 'name', 'module', 'description', 'created_at']


class PermissionCreateInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=150)
    module = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')


class PermissionUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    module = serializers.CharField(max_length=50, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class RoleOutputSerializer(serializers.ModelSerializer):
    permissions = PermissionOutputSerializer(many=True, read_only=True)
    permission_codes = serializers.SerializerMethodField()
    permissions_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'is_system_role',
            'permissions', 'permission_codes', 'permissions_count', 'created_at'
        ]

    def get_permission_codes(self, obj) -> list[str]:
        return list(obj.permissions.values_list('code', flat=True))

    def get_permissions_count(self, obj) -> int:
        return obj.permissions.count()


class RoleCreateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )


class RoleUpdateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )


class RoleAssignPermissionsInputSerializer(serializers.Serializer):
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )


class UserOutputSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='role_name', read_only=True)
    role_id = serializers.UUIDField(source='role.id', read_only=True, allow_null=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'role_id', 'role_display', 'assigned_country',
            'is_active', 'is_staff', 'is_superuser',
            'permissions', 'created_at', 'updated_at'
        ]

    def get_permissions(self, obj) -> list[str]:
        return obj.get_all_permissions()


class UserLoginInputSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserCreateInputSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    assigned_country = serializers.CharField(max_length=2, required=False, allow_null=True)
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )


class UserRoleAssignInputSerializer(serializers.Serializer):
    role = serializers.CharField(help_text="Role name (e.g. 'FINANCE_MANAGER') or Role UUID")
    assigned_country = serializers.CharField(max_length=2, required=False, allow_null=True)


class UserDirectPermissionsAssignInputSerializer(serializers.Serializer):
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )
