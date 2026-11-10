from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.selectors import (
    user_list, user_detail, role_list, role_detail,
    permission_list, permission_detail
)
from apps.users.services import UserService, RoleService, PermissionService
from apps.users.permissions import IsFinanceManagerOrAdmin, IsSuperUser
from apps.users.serializers import (
    UserOutputSerializer, UserCreateInputSerializer, UserUpdateInputSerializer,
    UserRoleAssignInputSerializer, UserDirectPermissionsAssignInputSerializer,
    UserDeactivateOutputSerializer,
    RoleOutputSerializer, RoleCreateInputSerializer, RoleUpdateInputSerializer,
    RoleAssignPermissionsInputSerializer,
    PermissionOutputSerializer, PermissionCreateInputSerializer, PermissionUpdateInputSerializer
)


# ============================================================================
# 1. PERMISSION MANAGEMENT (Superuser Exclusively)
# ============================================================================

class PermissionListCreateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    List all system permissions or create a new granular permission code.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Users - Permissions Admin'],
        operation_id='admin_permission_list',
        summary='List all system permissions',
        description='Returns a list of all granular system permissions, filterable by module.',
        parameters=[
            OpenApiParameter(name='module', description='Filter permissions by module domain (e.g. ledger, payroll)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: PermissionOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        module = request.query_params.get('module')
        perms = permission_list(module=module)
        return paginate_queryset(perms, request, PermissionOutputSerializer)

    @extend_schema(
        tags=['Users - Permissions Admin'],
        operation_id='admin_permission_create',
        summary='Create new permission code',
        description='Creates a new granular permission capability.',
        request=PermissionCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: PermissionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = PermissionCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perm = PermissionService.permission_create(**serializer.validated_data)
        return api_success(
            data=PermissionOutputSerializer(perm).data,
            message="Permission created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class PermissionDetailAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Retrieve, update, or remove a granular permission code.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Permissions Admin'],
        operation_id='admin_permission_detail',
        summary='Retrieve permission details',
        responses={
            status.HTTP_200_OK: PermissionOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, permission_id):
        perm = permission_detail(permission_id=permission_id)
        return api_success(data=PermissionOutputSerializer(perm).data, message="Permission retrieved successfully.")

    @extend_schema(
        tags=['Users - Permissions Admin'],
        operation_id='admin_permission_update',
        summary='Update permission details',
        request=PermissionUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: PermissionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, permission_id):
        serializer = PermissionUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perm = PermissionService.permission_update(permission_id=permission_id, **serializer.validated_data)
        return api_success(data=PermissionOutputSerializer(perm).data, message="Permission updated successfully.")

    @extend_schema(
        tags=['Users - Permissions Admin'],
        operation_id='admin_permission_partial_update',
        summary='Partially update permission details',
        request=PermissionUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: PermissionOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, permission_id):
        return self.put(request, permission_id)

    @extend_schema(
        tags=['Users - Permissions Admin'],
        operation_id='admin_permission_delete',
        summary='Delete permission',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def delete(self, request, permission_id):
        PermissionService.permission_delete(permission_id=permission_id)
        return api_success(message="Permission deleted successfully.", status_code=status.HTTP_200_OK)


# ============================================================================
# 2. ROLE MANAGEMENT (Superuser Exclusively)
# ============================================================================

class RoleListCreateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    List all enterprise roles or create a new role with associated permission codes.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_list',
        summary='List all enterprise roles',
        responses={
            status.HTTP_200_OK: RoleOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        roles = role_list()
        return paginate_queryset(roles, request, RoleOutputSerializer)

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_create',
        summary='Create new enterprise role',
        request=RoleCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: RoleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = RoleCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = RoleService.role_create(**serializer.validated_data)
        return api_success(
            data=RoleOutputSerializer(role).data,
            message="Role created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class RoleDetailAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Retrieve, update, or remove an enterprise role.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_detail',
        summary='Retrieve role details',
        responses={
            status.HTTP_200_OK: RoleOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, role_id):
        role = role_detail(role_id=role_id)
        return api_success(data=RoleOutputSerializer(role).data, message="Role retrieved successfully.")

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_update',
        summary='Update enterprise role',
        request=RoleUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: RoleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, role_id):
        serializer = RoleUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = RoleService.role_update(role_id=role_id, **serializer.validated_data)
        return api_success(data=RoleOutputSerializer(role).data, message="Role updated successfully.")

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_partial_update',
        summary='Partially update enterprise role',
        request=RoleUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: RoleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, role_id):
        return self.put(request, role_id)

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_delete',
        summary='Delete enterprise role',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def delete(self, request, role_id):
        RoleService.role_delete(role_id=role_id)
        return api_success(message="Role deleted successfully.", status_code=status.HTTP_200_OK)


class RoleAssignPermissionsAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Assign or synchronize a set of granular permission codes to an enterprise role.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Roles Admin'],
        operation_id='admin_role_assign_permissions',
        summary='Assign permission codes to an enterprise role',
        request=RoleAssignPermissionsInputSerializer,
        responses={
            status.HTTP_200_OK: RoleOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict
        }
    )
    def post(self, request, role_id):
        serializer = RoleAssignPermissionsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = RoleService.role_assign_permissions(role_id=role_id, **serializer.validated_data)
        return api_success(data=RoleOutputSerializer(role).data, message="Role permissions synchronized successfully.")



# ============================================================================
# 3. USER MANAGEMENT & ASSIGNMENT (Superuser Exclusively)
# ============================================================================

class UserListAdminApi(APIView):
    """Lists users with filtering by role and country."""
    permission_classes = [IsAuthenticated, IsFinanceManagerOrAdmin]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_list',
        summary='List users',
        description='Retrieves internal staff accounts with filtering by role, country, and active status.',
        parameters=[
            OpenApiParameter(name='role', description='Filter users by assigned role', required=False, type=str),
            OpenApiParameter(name='country', description='Filter users by country code (e.g. GH, CI)', required=False, type=str),
            OpenApiParameter(name='is_active', description='Filter active or inactive users (true/false)', required=False, type=bool)
        ],
        responses={
            status.HTTP_200_OK: UserOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        users = user_list(
            role=request.query_params.get('role'),
            country=request.query_params.get('country'),
            is_active=request.query_params.get('is_active')
        )
        return paginate_queryset(users, request, UserOutputSerializer)


class UserCreateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Provisions a new internal finance staff account with an assigned role and country.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_create',
        summary='Provision internal staff user',
        description='Creates a new staff user with password, primary role, country scoping, and optional direct permissions.',
        request=UserCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: UserOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        serializer = UserCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.user_create(**serializer.validated_data)
        return api_success(
            data=UserOutputSerializer(user).data,
            message="User provisioned successfully.",
            status_code=status.HTTP_201_CREATED
        )


class UserDetailAdminApi(APIView):
    """Get or modify an internal user's account."""
    permission_classes = [IsAuthenticated, IsFinanceManagerOrAdmin]

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_detail',
        summary='Retrieve user account',
        responses={
            status.HTTP_200_OK: UserOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, user_id):
        user = user_detail(user_id=user_id)
        return api_success(data=UserOutputSerializer(user).data, message="User retrieved successfully.")

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_update',
        summary='Update user account',
        request=UserUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: UserOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def put(self, request, user_id):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only a Superuser can modify user roles and country scoping."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.user_update(user_id=user_id, **serializer.validated_data)
        return api_success(data=UserOutputSerializer(user).data, message="User updated successfully.")

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_partial_update',
        summary='Partially update user account',
        request=UserUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: UserOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def patch(self, request, user_id):
        return self.put(request, user_id)

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_delete',
        summary='Delete user account',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, user_id):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only a Superuser can delete staff accounts."},
                status=status.HTTP_403_FORBIDDEN
            )
        UserService.user_delete(user_id=user_id)
        return api_success(message="User deleted successfully.", status_code=status.HTTP_200_OK)


class UserAssignRoleAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Assigns an enterprise role to a specific user.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_assign_role',
        summary='Assign role to user',
        request=UserRoleAssignInputSerializer,
        responses={
            status.HTTP_200_OK: UserOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict
        }
    )
    def post(self, request, user_id):
        serializer = UserRoleAssignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.user_assign_role(user_id=user_id, **serializer.validated_data)
        return api_success(data=UserOutputSerializer(user).data, message="Role assigned to user successfully.")


class UserAssignPermissionsAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Assigns direct granular permissions to a specific user.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_assign_permissions',
        summary='Assign direct permissions to user',
        request=UserDirectPermissionsAssignInputSerializer,
        responses={
            status.HTTP_200_OK: UserOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict
        }
    )
    def post(self, request, user_id):
        serializer = UserDirectPermissionsAssignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.user_assign_direct_permissions(user_id=user_id, **serializer.validated_data)
        return api_success(data=UserOutputSerializer(user).data, message="Direct permissions assigned successfully.")


class UserDeactivateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Deactivates user access.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Users - Users Admin'],
        operation_id='admin_user_deactivate',
        summary='Deactivate user account',
        request=None,
        responses={
            status.HTTP_200_OK: UserDeactivateOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, user_id):
        user = UserService.user_deactivate(user_id=user_id)
        return api_success(
            data={'status': 'DEACTIVATED', 'user_id': str(user.id)},
            message="User account deactivated successfully."
        )

