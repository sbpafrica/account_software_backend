import uuid
from django.conf import settings
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
                    organization_id = None, organization_role: str = None,
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

        if organization_id:
            from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
            from apps.users.models import UserRole
            org = Organization.objects.filter(id=organization_id).first()
            if org:
                org_role = organization_role or OrganizationRole.OWNER
                OrganizationMembership.objects.create(
                    organization=org,
                    user=user,
                    role=org_role,
                    is_default=True
                )
                if not resolved_role:
                    target_role = UserRole.ORGANIZATION_OWNER if org_role == 'OWNER' else UserRole.FINANCE_MANAGER
                    role_obj, _ = Role.objects.get_or_create(
                        name=target_role,
                        defaults={'description': f'Assigned {org_role}', 'is_system_role': True}
                    )
                    user.role = role_obj
                    user.save(update_fields=['role'])

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

    @staticmethod
    @transaction.atomic
    def password_change(*, user: User, current_password: str, new_password: str) -> None:
        """
        Allows an authenticated user to change their current password.
        Validates current password and updates with securely hashed new password.
        """
        if not user.check_password(current_password):
            raise ValidationError("Current password does not match.")
        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters long.")
        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])

    @staticmethod
    def password_forgot_request(*, email: str, frontend_url: str = None) -> bool:
        """
        Initiates a password reset workflow.
        Generates a secure, time-limited token and sends a reset link to the user's email.
        Always returns True to prevent email enumeration timing attacks.
        """
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from apps.common.tasks import send_email_task

        email_clean = email.strip().lower()
        user = User.objects.filter(email=email_clean, is_active=True).first()
        if not user:
            return True

        token = default_token_generator.make_token(user)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        base_url = frontend_url or getattr(settings, 'FRONTEND_URL', 'https://account.sbpafrica.group')
        reset_link = f"{base_url.rstrip('/')}/reset-password?uid={uidb64}&token={token}"

        subject = "Reset Your SBP-FMS Password"
        message = (
            f"Hello {user.first_name},\n\n"
            f"You requested a password reset for your SBP-FMS account.\n\n"
            f"Click the link below to set a new password:\n{reset_link}\n\n"
            f"This link will expire in 24 hours. If you did not request this, please ignore this email.\n\n"
            f"— SBP Africa Financial Systems"
        )
        html_message = (
            f"<p>Hello <strong>{user.first_name}</strong>,</p>"
            f"<p>You requested a password reset for your SBP-FMS account.</p>"
            f"<p><a href='{reset_link}' style='display:inline-block;padding:10px 20px;background:#2563EB;color:#fff;text-decoration:none;border-radius:6px;'>Reset Password</a></p>"
            f"<p style='color:#64748B;font-size:12px;'>If the button above does not work, copy and paste this URL into your browser:<br/>{reset_link}</p>"
        )

        try:
            send_email_task.delay(
                subject=subject,
                recipient_list=[user.email],
                message=message,
                html_message=html_message
            )
        except Exception:
            # Fallback direct send if celery broker unavailable
            from django.core.mail import send_mail
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'notifications@sbp-africa.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True
            )
        return True

    @staticmethod
    @transaction.atomic
    def password_reset_confirm(*, uidb64: str, token: str, new_password: str) -> None:
        """
        Validates the one-time token and sets the new password for the account.
        """
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str

        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters long.")

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.select_for_update().get(pk=uid, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise ValidationError("Invalid or expired password reset link.")

        if not default_token_generator.check_token(user, token):
            raise ValidationError("Invalid or expired password reset token.")

        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])

    @staticmethod
    @transaction.atomic
    def admin_reset_user_password(*, admin_user: User, user_id, new_password: str) -> User:
        """
        Allows an administrator or tenant owner to directly reset a subordinate user's password.
        """
        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters long.")

        user = User.objects.select_for_update().get(id=user_id)
        if user.is_superuser and not admin_user.is_superuser:
            raise ValidationError("Only platform Superusers can reset passwords of superusers.")

        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])
        return user


