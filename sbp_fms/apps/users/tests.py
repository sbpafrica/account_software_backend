import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User, Role, Permission, UserRole, DEFAULT_ROLE_PERMISSIONS
from apps.users.services import UserService, RoleService, PermissionService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="superadmin@sbp-africa.com",
        password="SuperPassword123!",
        first_name="Super",
        last_name="Admin"
    )


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        email="accountant@sbp-africa.com",
        password="UserPassword123!",
        first_name="Yaw",
        last_name="Accountant",
        assigned_country="GH"
    )


@pytest.fixture
def seed_rbac(db):
    read_perm = Permission.objects.create(code="ledger:read", name="Read Ledger", module="ledger")
    write_perm = Permission.objects.create(code="ledger:write", name="Write Ledger", module="ledger")
    disburse_perm = Permission.objects.create(code="payroll:disburse", name="Disburse Payroll", module="payroll")

    role = Role.objects.create(name="ACCOUNTANT_CUSTOM", description="Custom accountant role")
    role.permissions.add(read_perm, write_perm)
    return {
        "read_perm": read_perm,
        "write_perm": write_perm,
        "disburse_perm": disburse_perm,
        "role": role,
    }


@pytest.mark.django_db
class TestJWTAuthentication:
    def test_login_returns_jwt_tokens(self, api_client, regular_user):
        url = reverse("user-login")
        response = api_client.post(url, {
            "email": "accountant@sbp-africa.com",
            "password": "UserPassword123!"
        }, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "access" in data
        assert "refresh" in data
        assert "token" in data
        assert data["user"]["email"] == "accountant@sbp-africa.com"

    def test_login_fails_with_wrong_password(self, api_client, regular_user):
        url = reverse("user-login")
        response = api_client.post(url, {
            "email": "accountant@sbp-africa.com",
            "password": "WrongPassword!"
        }, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_jwt_token_refresh(self, api_client, regular_user):
        login_res = api_client.post(reverse("user-login"), {
            "email": "accountant@sbp-africa.com",
            "password": "UserPassword123!"
        }, format="json")
        refresh_token = login_res.data["data"]["refresh"]

        refresh_res = api_client.post(reverse("token-refresh"), {
            "refresh": refresh_token
        }, format="json")

        assert refresh_res.status_code == status.HTTP_200_OK
        assert "access" in refresh_res.data

    def test_jwt_protected_me_endpoint(self, api_client, regular_user):
        login_res = api_client.post(reverse("user-login"), {
            "email": "accountant@sbp-africa.com",
            "password": "UserPassword123!"
        }, format="json")
        access_token = login_res.data["data"]["access"]

        # Request with Bearer header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_res = api_client.get(reverse("user-me"))

        assert me_res.status_code == status.HTTP_200_OK
        assert me_res.data["data"]["user"]["email"] == "accountant@sbp-africa.com"


@pytest.mark.django_db
class TestRolesAndPermissionsRBAC:
    def test_superuser_can_create_permission(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)
        url = reverse("permission-list-create-admin")
        payload = {
            "code": "audit:export",
            "name": "Export Audit Logs",
            "module": "audit",
            "description": "Permission to export compliance audit trail"
        }
        res = api_client.post(url, payload, format="json")

        assert res.status_code == status.HTTP_201_CREATED
        assert Permission.objects.filter(code="audit:export").exists()

    def test_non_superuser_cannot_create_permission(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        url = reverse("permission-list-create-admin")
        payload = {
            "code": "audit:hack",
            "name": "Unauthorized Permission",
            "module": "audit"
        }
        res = api_client.post(url, payload, format="json")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert not Permission.objects.filter(code="audit:hack").exists()

    def test_superuser_can_create_role_with_permissions(self, api_client, superuser, seed_rbac):
        api_client.force_authenticate(user=superuser)
        url = reverse("role-list-create-admin")
        payload = {
            "name": "COMPLIANCE_OFFICER",
            "description": "Internal compliance monitoring role",
            "permission_codes": ["ledger:read", "payroll:disburse"]
        }
        res = api_client.post(url, payload, format="json")

        assert res.status_code == status.HTTP_201_CREATED
        role = Role.objects.get(name="COMPLIANCE_OFFICER")
        role_perm_codes = role.permissions.values_list("code", flat=True)
        assert "ledger:read" in role_perm_codes
        assert "payroll:disburse" in role_perm_codes

    def test_non_superuser_cannot_create_role(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        url = reverse("role-list-create-admin")
        payload = {
            "name": "HACKER_ROLE",
            "description": "Unauthorized role"
        }
        res = api_client.post(url, payload, format="json")

        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_superuser_can_assign_role_to_user(self, api_client, superuser, regular_user, seed_rbac):
        api_client.force_authenticate(user=superuser)
        role = seed_rbac["role"]

        assert not regular_user.has_permission_code("ledger:write")

        url = reverse("user-assign-role-admin", kwargs={"user_id": str(regular_user.id)})
        res = api_client.post(url, {"role": role.name}, format="json")

        assert res.status_code == status.HTTP_200_OK
        regular_user.refresh_from_db()
        assert regular_user.role == role
        assert regular_user.has_permission_code("ledger:read")
        assert regular_user.has_permission_code("ledger:write")
        assert not regular_user.has_permission_code("payroll:disburse")

    def test_superuser_can_assign_direct_permissions_to_user(self, api_client, superuser, regular_user, seed_rbac):
        api_client.force_authenticate(user=superuser)

        assert not regular_user.has_permission_code("payroll:disburse")

        url = reverse("user-assign-permissions-admin", kwargs={"user_id": str(regular_user.id)})
        res = api_client.post(url, {"permission_codes": ["payroll:disburse"]}, format="json")

        assert res.status_code == status.HTTP_200_OK
        regular_user.refresh_from_db()
        assert regular_user.has_permission_code("payroll:disburse")

    def test_superuser_has_all_permissions_wildcard(self, superuser):
        assert superuser.has_permission_code("any:random:permission")
        assert superuser.get_all_permissions() == ["*"]

    def test_functional_finance_manager_can_assign_role_and_permissions(self, api_client, regular_user, seed_rbac):
        # Create a functional user with FINANCE_MANAGER role (is_superuser=False)
        fm_role, _ = Role.objects.get_or_create(name=UserRole.FINANCE_MANAGER)
        finance_mgr = User.objects.create_user(
            email="fm@sbp-africa.com",
            password="Password123!",
            first_name="Finance",
            last_name="Manager",
            role=fm_role
        )
        api_client.force_authenticate(user=finance_mgr)

        role = seed_rbac["role"]
        # 1. Assign role
        url_role = reverse("user-assign-role-admin", kwargs={"user_id": str(regular_user.id)})
        res_role = api_client.post(url_role, {"role": role.name}, format="json")
        assert res_role.status_code == status.HTTP_200_OK

        # 2. Assign direct permissions
        url_perm = reverse("user-assign-permissions-admin", kwargs={"user_id": str(regular_user.id)})
        res_perm = api_client.post(url_perm, {"permission_codes": ["payroll:disburse"]}, format="json")
        assert res_perm.status_code == status.HTTP_200_OK

        regular_user.refresh_from_db()
        assert regular_user.role == role
        assert regular_user.has_permission_code("payroll:disburse")

    def test_functional_user_with_users_write_permission_can_assign_role(self, api_client, regular_user, seed_rbac):
        # Create an administrative user with direct 'users:write' permission (is_superuser=False, no admin role)
        users_write_perm, _ = Permission.objects.get_or_create(code="users:write", name="Write Users", module="users")
        hr_admin = User.objects.create_user(
            email="hr@sbp-africa.com",
            password="Password123!",
            first_name="HR",
            last_name="Officer"
        )
        hr_admin.direct_permissions.add(users_write_perm)

        api_client.force_authenticate(user=hr_admin)

        role = seed_rbac["role"]
        url_role = reverse("user-assign-role-admin", kwargs={"user_id": str(regular_user.id)})
        res_role = api_client.post(url_role, {"role": role.name}, format="json")
        assert res_role.status_code == status.HTTP_200_OK

        regular_user.refresh_from_db()
        assert regular_user.role == role

    def test_saas_tenant_owner_can_assign_role_and_permissions(self, api_client, regular_user, seed_rbac):
        from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
        from apps.organizations.context import set_current_organization, clear_current_organization

        org = Organization.objects.create(name="Delta Corp", base_currency="GHS")
        tenant_owner = User.objects.create_user(
            email="owner@delta.com",
            password="Password123!",
            first_name="Delta",
            last_name="Owner"
        )
        OrganizationMembership.objects.create(
            organization=org,
            user=tenant_owner,
            role=OrganizationRole.OWNER,
            is_default=True
        )

        api_client.force_authenticate(user=tenant_owner)
        set_current_organization(org)

        role = seed_rbac["role"]
        url_role = reverse("user-assign-role-admin", kwargs={"user_id": str(regular_user.id)})
        res_role = api_client.post(
            url_role,
            {"role": role.name},
            format="json",
            HTTP_X_ORGANIZATION_ID=str(org.id)
        )
        assert res_role.status_code == status.HTTP_200_OK

        clear_current_organization()
        regular_user.refresh_from_db()
        assert regular_user.role == role

    def test_organization_owner_has_all_business_permissions_but_no_superadmin_permissions(self, api_client):
        from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
        from apps.users.models import SUPERADMIN_PERMISSIONS, ALL_TENANT_BUSINESS_PERMISSIONS

        org = Organization.objects.create(name="Acme Corp", base_currency="GHS")
        owner_role, _ = Role.objects.get_or_create(
            name=UserRole.ORGANIZATION_OWNER,
            defaults={"is_system_role": True}
        )
        owner_user = User.objects.create_user(
            email="owner@acme.com",
            password="Password123!",
            first_name="Acme",
            last_name="Owner",
            role=owner_role
        )
        OrganizationMembership.objects.create(
            organization=org,
            user=owner_user,
            role=OrganizationRole.OWNER,
            is_default=True
        )

        # 1. Verify business permissions evaluate to True
        assert owner_user.has_permission_code("ledger:write") is True
        assert owner_user.has_permission_code("invoicing:create") is True
        assert owner_user.has_permission_code("payables:pay") is True
        assert owner_user.has_permission_code("assets:create") is True
        assert owner_user.has_permission_code("budgeting:approve") is True
        assert owner_user.has_permission_code("payroll:disburse") is True
        assert owner_user.has_permission_code("users:manage") is True

        # 2. Verify platform superadmin permissions evaluate to False
        assert owner_user.has_permission_code("*") is False
        assert owner_user.has_permission_code("audit:read") is False
        assert owner_user.has_permission_code("audit:all") is False
        assert owner_user.has_permission_code("roles:write") is False
        assert owner_user.has_permission_code("roles:manage") is False
        assert owner_user.has_permission_code("roles:assign_permissions") is False
        assert owner_user.has_permission_code("organizations:all") is False
        assert owner_user.has_permission_code("plans:write") is False

        # 3. Verify get_all_permissions contains all tenant business permissions and zero superadmin permissions
        all_perms = set(owner_user.get_all_permissions())
        assert "*" not in all_perms
        assert set(ALL_TENANT_BUSINESS_PERMISSIONS).issubset(all_perms)
        assert all_perms.intersection(SUPERADMIN_PERMISSIONS) == set()

        # 4. Verify API endpoints block the organization owner with 403 Forbidden
        api_client.force_authenticate(user=owner_user)

        # Roles & Permissions API
        role_res = api_client.get(reverse("role-list-create-admin"))
        assert role_res.status_code == status.HTTP_403_FORBIDDEN

        # Audit Logs API
        audit_res = api_client.get(reverse("audit-log-list-admin"))
        assert audit_res.status_code == status.HTTP_403_FORBIDDEN

        # Organizations Directory (Superadmin List) API
        orgs_res = api_client.get(reverse("organization-admin-list"))
        assert orgs_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPasswordManagement:

    def test_user_can_change_password(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        url = reverse("user-password-change")

        # 1. Fail with incorrect current password
        res_fail = api_client.post(url, {
            "current_password": "WrongPassword123!",
            "new_password": "BrandNewPassword123!"
        }, format="json")
        assert res_fail.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Succeed with correct current password
        res_ok = api_client.post(url, {
            "current_password": "UserPassword123!",
            "new_password": "BrandNewPassword123!"
        }, format="json")
        assert res_ok.status_code == status.HTTP_200_OK

        # 3. Authenticate with new password
        regular_user.refresh_from_db()
        assert regular_user.check_password("BrandNewPassword123!") is True

    def test_forgot_password_and_reset_confirm(self, api_client, regular_user):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        # 1. Request forgot password
        url_forgot = reverse("user-password-forgot")
        res_forgot = api_client.post(url_forgot, {"email": regular_user.email}, format="json")
        assert res_forgot.status_code == status.HTTP_200_OK

        # 2. Generate valid token & uid for confirm endpoint
        token = default_token_generator.make_token(regular_user)
        uidb64 = urlsafe_base64_encode(force_bytes(regular_user.pk))

        url_reset = reverse("user-password-reset-confirm")
        # Fail with short password
        res_short = api_client.post(url_reset, {
            "uid": uidb64,
            "token": token,
            "new_password": "short"
        }, format="json")
        assert res_short.status_code == status.HTTP_400_BAD_REQUEST

        # Succeed with valid password
        res_confirm = api_client.post(url_reset, {
            "uid": uidb64,
            "token": token,
            "new_password": "ResetNewPassword123!"
        }, format="json")
        assert res_confirm.status_code == status.HTTP_200_OK

        regular_user.refresh_from_db()
        assert regular_user.check_password("ResetNewPassword123!") is True

    def test_admin_reset_user_password(self, api_client, superuser, regular_user):
        api_client.force_authenticate(user=superuser)
        url = reverse("admin-user-reset-password", kwargs={"user_id": str(regular_user.id)})

        res = api_client.post(url, {"new_password": "AdminOverriddenPass123!"}, format="json")
        assert res.status_code == status.HTTP_200_OK

        regular_user.refresh_from_db()
        assert regular_user.check_password("AdminOverriddenPass123!") is True

