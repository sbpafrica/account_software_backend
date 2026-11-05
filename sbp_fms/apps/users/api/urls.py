from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.users.api.public import UserLoginPublicApi, UserMePublicApi
from apps.users.api.admin import (
    PermissionListCreateAdminApi, PermissionDetailAdminApi,
    RoleListCreateAdminApi, RoleDetailAdminApi, RoleAssignPermissionsAdminApi,
    UserListAdminApi, UserCreateAdminApi, UserDetailAdminApi,
    UserAssignRoleAdminApi, UserAssignPermissionsAdminApi, UserDeactivateAdminApi
)

urlpatterns = [
    # Public & JWT Authentication
    path('public/login/', UserLoginPublicApi.as_view(), name='user-login'),
    path('public/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('public/token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    path('public/me/', UserMePublicApi.as_view(), name='user-me'),

    # Permissions Management (Superuser Only)
    path('admin/permissions/', PermissionListCreateAdminApi.as_view(), name='permission-list-create-admin'),
    path('admin/permissions/<uuid:permission_id>/', PermissionDetailAdminApi.as_view(), name='permission-detail-admin'),

    # Roles Management & Permission Assignment (Superuser Only)
    path('admin/roles/', RoleListCreateAdminApi.as_view(), name='role-list-create-admin'),
    path('admin/roles/<uuid:role_id>/', RoleDetailAdminApi.as_view(), name='role-detail-admin'),
    path('admin/roles/<uuid:role_id>/assign-permissions/', RoleAssignPermissionsAdminApi.as_view(), name='role-assign-permissions-admin'),

    # Users Management & Role/Permission Assignment (Superuser Only)
    path('admin/users/', UserListAdminApi.as_view(), name='user-list-admin'),
    path('admin/users/create/', UserCreateAdminApi.as_view(), name='user-create-admin'),
    path('admin/users/<uuid:user_id>/', UserDetailAdminApi.as_view(), name='user-detail-admin'),
    path('admin/users/<uuid:user_id>/assign-role/', UserAssignRoleAdminApi.as_view(), name='user-assign-role-admin'),
    path('admin/users/<uuid:user_id>/assign-permissions/', UserAssignPermissionsAdminApi.as_view(), name='user-assign-permissions-admin'),
    path('admin/users/<uuid:user_id>/deactivate/', UserDeactivateAdminApi.as_view(), name='user-deactivate-admin'),
]
