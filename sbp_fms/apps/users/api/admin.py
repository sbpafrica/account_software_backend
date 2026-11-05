from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.users.selectors import (
    user_list, user_detail, role_list, role_detail,
    permission_list, permission_detail
)
from apps.users.services import UserService, RoleService, PermissionService
from apps.users.permissions import IsFinanceManagerOrAdmin, IsSuperUser
from apps.users.serializers import (
    UserOutputSerializer, UserCreateInputSerializer, UserRoleAssignInputSerializer,
    UserDirectPermissionsAssignInputSerializer,
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

    def get(self, request):
        module = request.query_params.get('module')
        perms = permission_list(module=module)
        return Response(PermissionOutputSerializer(perms, many=True).data)

    def post(self, request):
        serializer = PermissionCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            perm = PermissionService.permission_create(**serializer.validated_data)
            return Response(PermissionOutputSerializer(perm).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class PermissionDetailAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Retrieve, update, or remove a granular permission code.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request, permission_id):
        perm = permission_detail(permission_id=permission_id)
        return Response(PermissionOutputSerializer(perm).data)

    def put(self, request, permission_id):
        serializer = PermissionUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            perm = PermissionService.permission_update(permission_id=permission_id, **serializer.validated_data)
            return Response(PermissionOutputSerializer(perm).data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, permission_id):
        PermissionService.permission_delete(permission_id=permission_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# 2. ROLE MANAGEMENT (Superuser Exclusively)
# ============================================================================

class RoleListCreateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    List all enterprise roles or create a new role with associated permission codes.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request):
        roles = role_list()
        return Response(RoleOutputSerializer(roles, many=True).data)

    def post(self, request):
        serializer = RoleCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            role = RoleService.role_create(**serializer.validated_data)
            return Response(RoleOutputSerializer(role).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class RoleDetailAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Retrieve, update, or remove an enterprise role.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request, role_id):
        role = role_detail(role_id=role_id)
        return Response(RoleOutputSerializer(role).data)

    def put(self, request, role_id):
        serializer = RoleUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            role = RoleService.role_update(role_id=role_id, **serializer.validated_data)
            return Response(RoleOutputSerializer(role).data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, role_id):
        try:
            RoleService.role_delete(role_id=role_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class RoleAssignPermissionsAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Assign or synchronize a set of granular permission codes to an enterprise role.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, role_id):
        serializer = RoleAssignPermissionsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            role = RoleService.role_assign_permissions(role_id=role_id, **serializer.validated_data)
            return Response(RoleOutputSerializer(role).data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# 3. USER MANAGEMENT & ASSIGNMENT (Superuser Exclusively)
# ============================================================================

class UserListAdminApi(APIView):
    """Lists users with filtering by role and country."""
    permission_classes = [IsAuthenticated, IsFinanceManagerOrAdmin]

    def get(self, request):
        users = user_list(
            role=request.query_params.get('role'),
            country=request.query_params.get('country')
        )
        return Response(UserOutputSerializer(users, many=True).data)


class UserCreateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Provisions a new internal finance staff account with an assigned role and country.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        serializer = UserCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = UserService.user_create(**serializer.validated_data)
            return Response(UserOutputSerializer(user).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class UserDetailAdminApi(APIView):
    """Get or modify an internal user's account."""
    permission_classes = [IsAuthenticated, IsFinanceManagerOrAdmin]

    def get(self, request, user_id):
        user = user_detail(user_id=user_id)
        return Response(UserOutputSerializer(user).data)

    def put(self, request, user_id):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only a Superuser can modify user roles and country scoping."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserRoleAssignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = UserService.user_assign_role(user_id=user_id, **serializer.validated_data)
            return Response(UserOutputSerializer(user).data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class UserAssignRoleAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Assigns an enterprise role to a specific user.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, user_id):
        serializer = UserRoleAssignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = UserService.user_assign_role(user_id=user_id, **serializer.validated_data)
            return Response(UserOutputSerializer(user).data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class UserAssignPermissionsAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Assigns direct granular permissions to a specific user.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, user_id):
        serializer = UserDirectPermissionsAssignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = UserService.user_assign_direct_permissions(user_id=user_id, **serializer.validated_data)
            return Response(UserOutputSerializer(user).data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


class UserDeactivateAdminApi(APIView):
    """
    [SUPERUSER ONLY]:
    Deactivates user access.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, user_id):
        user = UserService.user_deactivate(user_id=user_id)
        return Response({'status': 'DEACTIVATED', 'user_id': str(user.id)})
