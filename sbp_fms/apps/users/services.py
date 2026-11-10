import uuid
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from .models import User, Role, Permission, UserRole
from .authentication import JWTTokenService


class PermissionService:
    @staticmethod
    @transaction.atomic
    def permission_create(*, code: str, name: str, module: str = '', description: str = '') -> Permission:
        code = code.strip().lower()
        if Permission.objects.filter(code=code).exists():
            raise ValidationError(f"A permission with code '{code}' already exists.")
        permission = Permission.objects.create(
            code=code,
            name=name.strip(),
            module=module.strip().lower(),
            description=description.strip()
        )
        CacheManager.invalidate_users()
        return permission

    @staticmethod
    @transaction.atomic
    def permission_update(*, permission_id, name: str = None, module: str = None, description: str = None) -> Permission:
        permission = Permission.objects.select_for_update().get(id=permission_id)
        if name is not None:
            permission.name = name.strip()
        if module is not None:
            permission.module = module.strip().lower()
        if description is not None:
            permission.description = description.strip()
        permission.save()
        CacheManager.invalidate_users()
        return permission

    @staticmethod
    @transaction.atomic
    def permission_delete(*, permission_id) -> None:
        permission = Permission.objects.get(id=permission_id)
        permission.delete()
        CacheManager.invalidate_users()


class RoleService:
    @staticmethod
    @transaction.atomic
    def role_create(*, name: str, description: str = '', permission_codes: list[str] = None) -> Role:
        name = name.strip().upper()
        if Role.objects.filter(name=name).exists():
            raise ValidationError(f"A role with name '{name}' already exists.")
        role = Role.objects.create(
            name=name,
            description=description.strip()
        )
        if permission_codes:
            perms = Permission.objects.filter(code__in=[p.strip().lower() for p in permission_codes])
            role.permissions.set(perms)
        CacheManager.invalidate_users()
        return role

    @staticmethod
    @transaction.atomic
    def role_update(*, role_id, name: str = None, description: str = None,
                    permission_codes: list[str] = None) -> Role:
        role = Role.objects.select_for_update().get(id=role_id)
        if name is not None:
            new_name = name.strip().upper()
            if Role.objects.filter(name=new_name).exclude(id=role_id).exists():
                raise ValidationError(f"A role with name '{new_name}' already exists.")
            role.name = new_name
        if description is not None:
            role.description = description.strip()
        role.save()

        if permission_codes is not None:
            perms = Permission.objects.filter(code__in=[p.strip().lower() for p in permission_codes])
            role.permissions.set(perms)

        CacheManager.invalidate_users()
        return role

    @staticmethod
    @transaction.atomic
    def role_delete(*, role_id) -> None:
        role = Role.objects.get(id=role_id)
        if role.is_system_role:
            raise ValidationError(f"System role '{role.name}' cannot be deleted.")
        if role.users.exists():
            raise ValidationError(f"Cannot delete role '{role.name}' because it is assigned to active users.")
        role.delete()
        CacheManager.invalidate_users()

    @staticmethod
    @transaction.atomic
    def role_assign_permissions(*, role_id, permission_codes: list[str]) -> Role:
        role = Role.objects.select_for_update().get(id=role_id)
        perms = Permission.objects.filter(code__in=[p.strip().lower() for p in permission_codes])
        role.permissions.set(perms)
        CacheManager.invalidate_users()
        return role


class UserService:
    @staticmethod
    def _resolve_role(role_val) -> Role | None:
        if not role_val:
            return None
        if isinstance(role_val, Role):
            return role_val
        try:
            val_uuid = uuid.UUID(str(role_val))
            return Role.objects.get(id=val_uuid)
        except (ValueError, Role.DoesNotExist):
            pass
        role_name = str(role_val).strip().upper()
        role_obj, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={'description': f'Role {role_name}'}
        )
        return role_obj

    @staticmethod
    @transaction.atomic
    def user_create(*, email: str, password: str, first_name: str, last_name: str,
                    role: str | Role = None, assigned_country: str = None,
                    permission_codes: list[str] = None) -> User:
        if User.objects.filter(email=email).exists():
            raise ValidationError(f"A user with email '{email}' already exists.")

        resolved_role = UserService._resolve_role(role)

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=resolved_role,
            assigned_country=assigned_country
        )

        if permission_codes:
            perms = Permission.objects.filter(code__in=[p.strip().lower() for p in permission_codes])
            user.direct_permissions.set(perms)

        CacheManager.invalidate_users()
        return user

    @staticmethod
    def user_authenticate(*, email: str, password: str) -> tuple[User, dict]:
        try:
            user = User.objects.get(email=email, is_active=True)
            if not user.check_password(password):
                raise ValidationError("Invalid email or password.")
            tokens = JWTTokenService.get_tokens_for_user(user)
            return user, tokens
        except User.DoesNotExist:
            raise ValidationError("Invalid email or password.")

    @staticmethod
    @transaction.atomic
    def user_assign_role(*, user_id, role, assigned_country: str = None) -> User:
        user = User.objects.select_for_update().get(id=user_id)
        resolved_role = UserService._resolve_role(role)
        user.role = resolved_role
        if assigned_country is not None:
            user.assigned_country = assigned_country
        user.save(update_fields=['role', 'assigned_country', 'updated_at'])
        CacheManager.invalidate_users()
        return user

    @staticmethod
    @transaction.atomic
    def user_update_role(*, user_id, new_role: str, assigned_country: str = None) -> User:
        return UserService.user_assign_role(user_id=user_id, role=new_role, assigned_country=assigned_country)

    @staticmethod
    @transaction.atomic
    def user_assign_direct_permissions(*, user_id, permission_codes: list[str]) -> User:
        user = User.objects.select_for_update().get(id=user_id)
        perms = Permission.objects.filter(code__in=[p.strip().lower() for p in permission_codes])
        user.direct_permissions.set(perms)
        CacheManager.invalidate_users()
        return user

    @staticmethod
    @transaction.atomic
    def user_update(*, user_id, first_name: str = None, last_name: str = None,
                    role = None, assigned_country: str = None, is_active: bool = None) -> User:
        user = User.objects.select_for_update().get(id=user_id)
        if first_name is not None:
            user.first_name = first_name.strip()
        if last_name is not None:
            user.last_name = last_name.strip()
        if role is not None:
            user.role = UserService._resolve_role(role)
        if assigned_country is not None:
            user.assigned_country = assigned_country.strip().upper() if assigned_country else None
        if is_active is not None:
            user.is_active = is_active
        user.save()
        CacheManager.invalidate_users()
        return user

    @staticmethod
    @transaction.atomic
    def user_delete(*, user_id) -> None:
        user = User.objects.get(id=user_id)
        if user.is_superuser:
            raise ValidationError("Superuser accounts cannot be permanently deleted.")
        user.delete()
        CacheManager.invalidate_users()

    @staticmethod
    @transaction.atomic
    def user_deactivate(*, user_id) -> User:
        user = User.objects.select_for_update().get(id=user_id)
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])
        CacheManager.invalidate_users()
        return user

