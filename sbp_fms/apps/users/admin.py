from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.users.models import User, Role, Permission


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role_assigned', 'assigned_country', 'is_staff', 'is_superuser', 'is_stakeholder', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_stakeholder', 'role', 'assigned_country')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    @admin.display(description='Role')
    def role_assigned(self, obj):
        return obj.get_role_display()

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'assigned_country')}),
        ('Permissions & Roles', {'fields': (
            'role', 'roles',
            'is_active', 'is_staff', 'is_superuser', 'is_stakeholder',
            'user_permissions',
        )}),
        ('Important Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at', 'last_login')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'role', 'is_staff', 'is_superuser'),
        }),
    )
    filter_horizontal = ('roles', 'user_permissions')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Tenant isolation: Only display users belonging to the tenant organization(s) of this admin
            return qs.filter(
                organization_memberships__organization__memberships__user=request.user
            ).distinct()
        return qs

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            # Non-superusers cannot escalate privileges or alter platform-level flags
            return (
                (None, {'fields': ('email', 'password')}),
                ('Personal Info', {'fields': ('first_name', 'last_name', 'assigned_country')}),
                ('Status & Role', {'fields': ('role', 'is_active')}),
                ('Important Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
            )
        return fieldsets

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj and (obj.is_superuser or obj.is_staff):
                return False
        return super().has_delete_permission(request, obj)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_system_role', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_system_role',)
    filter_horizontal = ('permissions',)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'module', 'created_at')
    search_fields = ('code', 'name', 'module')
    list_filter = ('module',)

    def has_module_permission(self, request):
        return request.user.is_superuser
