from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from apps.common.models import BaseModel


class Permission(BaseModel):
    """
    [GRANULAR RBAC PERMISSION]:
    Represents an authorized capability across SBP-FMS (e.g., 'ledger:read', 'payroll:disburse').
    Created and managed dynamically by the Superuser.
    """
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    module = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Functional domain e.g. 'ledger', 'payroll', 'payables', 'receivables', 'treasury', 'tax', 'users'"
    )
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['module', 'code']

    def __str__(self):
        return f"{self.code} ({self.name})"


class Role(BaseModel):
    """
    [ENTERPRISE ROLE]:
    Groups one or more granular permissions.
    Created, updated, and assigned to users exclusively by the Superuser.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')
    is_system_role = models.BooleanField(
        default=False,
        help_text="Flag indicating core default system roles"
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, Role):
            return self.id == other.id
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.name)


class UserRole:
    """Standard predefined role name constants for seeding and backwards compatibility."""
    SUPER_ADMIN = 'SUPER_ADMIN'
    FINANCE_MANAGER = 'FINANCE_MANAGER'
    CHIEF_ACCOUNTANT = 'CHIEF_ACCOUNTANT'
    AR_OFFICER = 'AR_OFFICER'
    AP_OFFICER = 'AP_OFFICER'
    PAYROLL_ACCOUNTANT = 'PAYROLL_ACCOUNTANT'
    TREASURY_OFFICER = 'TREASURY_OFFICER'
    INTERNAL_AUDITOR = 'INTERNAL_AUDITOR'
    COUNTRY_ACCOUNTANT = 'COUNTRY_ACCOUNTANT'

    CHOICES = (
        (SUPER_ADMIN, 'Super Admin (CEO / Board)'),
        (FINANCE_MANAGER, 'Finance Manager'),
        (CHIEF_ACCOUNTANT, 'Chief Accountant'),
        (AR_OFFICER, 'Accounts Receivable Officer'),
        (AP_OFFICER, 'Accounts Payable Officer'),
        (PAYROLL_ACCOUNTANT, 'Payroll Accountant'),
        (TREASURY_OFFICER, 'Treasury Officer'),
        (INTERNAL_AUDITOR, 'Internal Auditor (Read-Only)'),
        (COUNTRY_ACCOUNTANT, 'Country Accountant'),
    )


# Default initial permission code mappings
DEFAULT_ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: ['*'],
    UserRole.FINANCE_MANAGER: [
        'ledger:read', 'ledger:write', 'ledger:approve', 'ledger:reverse',
        'payroll:read', 'payroll:disburse',
        'payables:read', 'payables:approve', 'payables:pay',
        'receivables:read', 'receivables:write',
        'treasury:read', 'treasury:write', 'treasury:forecast',
        'reports:all', 'users:read', 'users:write'
    ],
    UserRole.CHIEF_ACCOUNTANT: [
        'ledger:read', 'ledger:write', 'ledger:reverse',
        'payroll:read', 'payables:read', 'receivables:read',
        'treasury:read', 'reports:all'
    ],
    UserRole.PAYROLL_ACCOUNTANT: [
        'payroll:read', 'payroll:create', 'ledger:read'
    ],
    UserRole.AP_OFFICER: [
        'payables:read', 'payables:create', 'payables:match'
    ],
    UserRole.AR_OFFICER: [
        'receivables:read', 'receivables:create'
    ],
    UserRole.TREASURY_OFFICER: [
        'treasury:read', 'treasury:write', 'treasury:reconcile', 'treasury:forecast'
    ],
    UserRole.INTERNAL_AUDITOR: [
        # Read-only across everything, zero write or approve permissions!
        'ledger:read', 'payroll:read', 'payables:read', 'receivables:read',
        'treasury:read', 'tax:read', 'reports:all', 'audit:read'
    ],
    UserRole.COUNTRY_ACCOUNTANT: [
        'ledger:read', 'ledger:write', 'payables:read', 'payables:create',
        'receivables:read', 'receivables:create'
    ]
}

ROLE_PERMISSIONS = DEFAULT_ROLE_PERMISSIONS


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is strictly required')
        email = self.normalize_email(email)

        role = extra_fields.pop('role', None)
        roles = extra_fields.pop('roles', None)
        direct_permissions = extra_fields.pop('direct_permissions', None)

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        if role is not None:
            if isinstance(role, str):
                role_obj, _ = Role.objects.get_or_create(
                    name=role,
                    defaults={'description': f'Role {role}', 'is_system_role': True}
                )
                user.role = role_obj
            elif isinstance(role, Role):
                user.role = role

        user.save(using=self._db)

        if roles:
            user.roles.set(roles)
        if direct_permissions:
            user.direct_permissions.set(direct_permissions)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        role = extra_fields.pop('role', None)

        user = self.create_user(email, password, **extra_fields)

        if role is None:
            super_role, _ = Role.objects.get_or_create(
                name=UserRole.SUPER_ADMIN,
                defaults={'description': 'Super Admin (CEO / Board)', 'is_system_role': True}
            )
            user.role = super_role
        elif isinstance(role, str):
            role_obj, _ = Role.objects.get_or_create(
                name=role,
                defaults={'description': f'Role {role}', 'is_system_role': True}
            )
            user.role = role_obj
        elif isinstance(role, Role):
            user.role = role

        user.save(update_fields=['role'])
        return user


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """
    [CUSTOM USER MODEL]:
    Inherits UUID and timestamps from BaseModel.
    Contains dynamic Role, optional Multi-Roles, Direct Permissions, and Country Scope.
    Roles and Permissions are created and assigned by the Superuser.
    """
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Primary role assigned to the user by a Superuser."
    )
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='multi_role_users',
        help_text="Optional additional roles assigned to the user."
    )
    direct_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='direct_users',
        help_text="Granular permissions assigned directly to this user by a Superuser."
    )
    assigned_country = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="Two-letter ISO country code (e.g., 'GH', 'NG', 'CI'). Null means all countries (Group level)."
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        ordering = ['email']

    def __str__(self):
        role_label = self.role.name if self.role else ("SUPER_ADMIN" if self.is_superuser else "NO_ROLE")
        return f"{self.email} ({role_label})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def role_name(self) -> str | None:
        return self.role.name if self.role else None

    def get_role_display(self) -> str:
        if self.role:
            return self.role.name
        if self.is_superuser:
            return "Super Admin (CEO / Board)"
        return "No Role"

    def get_all_permissions(self) -> list[str]:
        """
        Returns all unique permission codes available to this user,
        aggregating from superuser status, primary role, secondary roles, and direct permissions.
        """
        if not self.is_active:
            return []
        if self.is_superuser or (self.role and self.role.name == UserRole.SUPER_ADMIN):
            return ['*']

        perm_codes = set()
        if self.role:
            perm_codes.update(self.role.permissions.values_list('code', flat=True))

        if self.pk:
            perm_codes.update(self.roles.values_list('permissions__code', flat=True))
            perm_codes.update(self.direct_permissions.values_list('code', flat=True))

        # Filter out any None values resulting from empty relation joins
        perm_codes.discard(None)
        if '*' in perm_codes:
            return ['*']
        return sorted(list(perm_codes))

    def has_permission_code(self, perm_code: str) -> bool:
        """
        Evaluates whether the user possesses a specific permission code.
        """
        if not self.is_active:
            return False
        if self.is_superuser or (self.role and self.role.name == UserRole.SUPER_ADMIN):
            return True

        if self.role:
            if self.role.permissions.filter(code__in=[perm_code, '*']).exists():
                return True

        if self.pk:
            if self.roles.filter(permissions__code__in=[perm_code, '*']).exists():
                return True
            if self.direct_permissions.filter(code__in=[perm_code, '*']).exists():
                return True

        return False

    def can_access_country(self, country_code: str) -> bool:
        """
        Enforces Multi-Tenant Country Scoping:
        Group roles (CEO, Finance Manager, Auditor) have access to ALL countries.
        Country Accountants are locked strictly to their assigned country.
        """
        if self.is_superuser:
            return True
        role_name = self.role.name if self.role else ""
        if not self.assigned_country or role_name in [UserRole.SUPER_ADMIN, UserRole.FINANCE_MANAGER, UserRole.INTERNAL_AUDITOR]:
            return True
        return self.assigned_country.upper() == country_code.upper()
