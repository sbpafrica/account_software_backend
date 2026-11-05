from rest_framework import permissions
from .models import UserRole


class IsSuperUser(permissions.BasePermission):
    """
    [SUPERUSER PERMISSION]:
    Allows access strictly to authenticated Superusers.
    Used for creating and assigning enterprise roles, granular permissions, and managing staff.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class HasPermissionCode:
    """
    Factory returning a DRF Permission class checking user.has_permission_code(perm_code).
    Superusers bypass and automatically evaluate to True.
    """
    def __init__(self, perm_code: str):
        self.perm_code = perm_code

    def __call__(self):
        code = self.perm_code
        class CustomPerm(permissions.BasePermission):
            def has_permission(self, request, view):
                if not request.user or not request.user.is_authenticated:
                    return False
                return request.user.has_permission_code(code)
        return CustomPerm


class HasRole:
    """
    Factory returning a DRF Permission class verifying user's role is in allowed_roles.
    Superusers automatically evaluate to True.
    """
    def __init__(self, *allowed_roles):
        self.allowed_roles = allowed_roles

    def __call__(self):
        roles = self.allowed_roles
        class RolePerm(permissions.BasePermission):
            def has_permission(self, request, view):
                if not request.user or not request.user.is_authenticated:
                    return False
                if request.user.is_superuser:
                    return True
                user_role = request.user.role.name if request.user.role else None
                return user_role in roles or user_role == UserRole.SUPER_ADMIN
        return RolePerm


class IsFinanceManagerOrAdmin(permissions.BasePermission):
    """
    Checks if authenticated user is Superuser or has the Finance Manager role.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        user_role = request.user.role.name if request.user.role else None
        return user_role in [UserRole.SUPER_ADMIN, UserRole.FINANCE_MANAGER]


class CountryScopedAccess(permissions.BasePermission):
    """
    Prevents a country accountant from viewing or posting records for an unauthorized country.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        country_param = request.query_params.get('country') or request.data.get('country_code')
        if country_param and not user.can_access_country(country_param):
            return False
        return True


class SegregationOfDuties:
    """
    [SEGREGATION OF DUTIES]: Ensures the user approving or disbursing a transaction
    is NOT the same user who prepared/created it. Superusers are exempt.
    """
    @staticmethod
    def validate(created_by_user, current_user, action_name="approve"):
        is_super = current_user.is_superuser or (
            current_user.role and current_user.role.name == UserRole.SUPER_ADMIN
        )
        if created_by_user == current_user and not is_super:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f"Segregation of Duties Violation: You cannot {action_name} a transaction that you created."
            )
