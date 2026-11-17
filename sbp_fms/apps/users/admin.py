from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.users.models import User, Role, Permission


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'assigned_country', 'is_staff', 'is_superuser', 'is_stakeholder', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_stakeholder', 'role', 'assigned_country')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

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


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_system_role', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_system_role',)
    filter_horizontal = ('permissions',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'module', 'created_at')
    search_fields = ('code', 'name', 'module')
    list_filter = ('module',)
