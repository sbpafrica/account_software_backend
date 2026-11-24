import datetime
import pytest
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User
from apps.users.authentication import JWTTokenService
from apps.organizations.models import (
    Organization, SubscriptionPlan, SubscriptionPlanTier, OrganizationRole,
    OrganizationMembership, OrganizationInvitation
)
from apps.organizations.services import OrganizationService
from apps.organizations.context import get_current_organization, set_current_organization, clear_current_organization
from apps.ledger.models import CompanyProfile


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def saas_owner(db):
    org, user, tokens = OrganizationService.register_customer(
        organization_name="Acme Global Inc",
        email="owner@acme.com",
        password="SecurePassword123!",
        first_name="Alice",
        last_name="Owner",
        country_code="GH",
        base_currency="GHS"
    )
    return {
        'org': org,
        'user': user,
        'tokens': tokens,
    }


@pytest.fixture
def secondary_org(db, saas_owner):
    org2 = Organization.objects.create(
        name="Beta Holdings Ltd",
        plan=SubscriptionPlanTier.GROWTH,
        base_currency="USD",
        billing_email="billing@betaholdings.com"
    )
    # Give Alice membership in Beta Holdings too
    OrganizationMembership.objects.create(
        organization=org2,
        user=saas_owner['user'],
        role=OrganizationRole.ADMIN,
        is_default=False
    )
    return org2


@pytest.mark.django_db
class TestOrganizationService:
    def test_register_customer_success(self):
        org, user, tokens = OrganizationService.register_customer(
            organization_name="Zenith Corp",
            email="ceo@zenith.com",
            password="StrongPassword123!",
            first_name="Zack",
            last_name="Zenith",
            country_code="NG",
            base_currency="NGN",
            subdomain="zenith"
        )
        assert org.name == "Zenith Corp"
        assert org.slug.startswith("zenith")
        assert org.subdomain == "zenith"
        assert org.plan == SubscriptionPlanTier.TRIAL
        assert org.plan_expires_at is not None

        # Verify user and membership
        assert user.email == "ceo@zenith.com"
        assert user.assigned_country == "NG"
        membership = OrganizationMembership.objects.get(organization=org, user=user)
        assert membership.role == OrganizationRole.OWNER
        assert membership.is_default is True

        # Verify company profile was initialized
        profile = CompanyProfile.all_objects.filter(organization=org).first()
        assert profile is not None
        assert profile.company_name == "Zenith Corp"
        assert profile.base_currency == "NGN"

        # Verify JWT tokens contain tenant claims
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(tokens['access'])
        assert str(access_token['org_id']) == str(org.id)
        assert access_token['org_slug'] == org.slug
        assert access_token['org_role'] == OrganizationRole.OWNER

    def test_switch_organization(self, saas_owner, secondary_org):
        user = saas_owner['user']
        result = OrganizationService.switch_organization(
            user=user,
            organization_id=secondary_org.id
        )
        assert result['organization'].id == secondary_org.id
        assert result['role'] == OrganizationRole.ADMIN

        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken(result['tokens']['access'])
        assert str(token['org_id']) == str(secondary_org.id)
        assert token['org_role'] == OrganizationRole.ADMIN

    def test_invite_and_accept_member(self, saas_owner):
        owner = saas_owner['user']
        org = saas_owner['org']

        # Invite Bob
        invitation = OrganizationService.invite_member(
            organization_id=org.id,
            email="bob@acme.com",
            role=OrganizationRole.ACCOUNTANT,
            invited_by=owner
        )
        assert invitation.email == "bob@acme.com"
        assert invitation.accepted is False
        assert invitation.token is not None

        # Create Bob user account and accept
        bob = User.objects.create_user(
            email="bob@acme.com",
            password="Password123!",
            first_name="Bob",
            last_name="Accountant"
        )
        membership = OrganizationService.accept_invitation(
            token=str(invitation.token),
            user=bob
        )
        assert membership.organization == org
        assert membership.user == bob
        assert membership.role == OrganizationRole.ACCOUNTANT

        invitation.refresh_from_db()
        assert invitation.accepted is True


@pytest.mark.django_db
class TestOrganizationEndpoints:
    def test_public_registration_endpoint(self, api_client):
        url = reverse('organization-register-public')
        payload = {
            'organization_name': 'Horizon Logistics',
            'email': 'admin@horizonlogistics.com',
            'password': 'StrongPassword123!',
            'first_name': 'Hellen',
            'last_name': 'Otieno',
            'country_code': 'KE',
            'base_currency': 'KES',
            'subdomain': 'horizon'
        }
        res = api_client.post(url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        body = res.json()
        assert body['success'] is True
        assert body['data']['organization']['name'] == 'Horizon Logistics'
        assert 'access' in body['data']
        assert 'refresh' in body['data']

    def test_my_organizations_endpoint(self, api_client, saas_owner, secondary_org):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {saas_owner['tokens']['access']}")
        url = reverse('organization-me-list')
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert len(data) == 2
        org_names = [m['organization']['name'] for m in data]
        assert "Acme Global Inc" in org_names
        assert "Beta Holdings Ltd" in org_names

    def test_switch_organization_endpoint(self, api_client, saas_owner, secondary_org):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {saas_owner['tokens']['access']}")
        url = reverse('organization-switch')
        res = api_client.post(url, {'organization_id': str(secondary_org.id)}, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert data['organization']['name'] == 'Beta Holdings Ltd'
        assert data['role'] == OrganizationRole.ADMIN
        assert 'access' in data

    def test_tenant_isolation(self, saas_owner, secondary_org):
        org1 = saas_owner['org']
        org2 = secondary_org

        # Profile for org 2
        CompanyProfile.objects.create(
            organization=org2,
            company_name="Beta Subsidiary",
            country_code="GH",
            base_currency="USD"
        )

        # In context of org 1
        set_current_organization(org1)
        profiles_org1 = list(CompanyProfile.objects.all())
        assert len(profiles_org1) == 1
        assert profiles_org1[0].company_name == "Acme Global Inc"

        # In context of org 2
        set_current_organization(org2)
        profiles_org2 = list(CompanyProfile.objects.all())
        assert len(profiles_org2) == 1
        assert profiles_org2[0].company_name == "Beta Subsidiary"

        clear_current_organization()

    def test_30_days_trial_expiration_enforcement(self, api_client, saas_owner):
        org = saas_owner['org']
        tokens = saas_owner['tokens']
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 1. While within 30-day trial: active and operations work
        assert org.is_subscription_active is True
        assert org.is_trial is True
        assert org.days_remaining >= 28

        # 2. Expire the trial artificially
        org.plan_expires_at = timezone.now() - datetime.timedelta(days=1)
        org.save()
        assert org.is_subscription_active is False
        assert org.days_remaining == 0

        # 3. Financial operations locked with HTTP 402 Payment Required
        res = api_client.get(f"/api/v1/ledger/public/accounts/?organization_id={org.id}")
        assert res.status_code == 402
        data = res.json()
        assert data['code'] == 'SUBSCRIPTION_EXPIRED'

        # 4. Billing, plans, and tenant profile endpoints remain unlocked so they can subscribe
        res_me = api_client.get("/api/v1/organizations/me/")
        assert res_me.status_code == 200

        res_plans = api_client.get("/api/v1/organizations/plans/")
        assert res_plans.status_code == 200

    def test_organization_update_put_and_patch(self, api_client, saas_owner):
        org = saas_owner['org']
        tokens = saas_owner['tokens']
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # PATCH update
        url = reverse('organization-detail', kwargs={'organization_id': org.id})
        res_patch = api_client.patch(url, {'name': 'Acme Global Updated'}, format='json')
        assert res_patch.status_code == status.HTTP_200_OK
        assert res_patch.json()['data']['name'] == 'Acme Global Updated'

        # PUT full update
        res_put = api_client.put(url, {'name': 'Acme Enterprise', 'base_currency': 'USD'}, format='json')
        assert res_put.status_code == status.HTTP_200_OK
        assert res_put.json()['data']['name'] == 'Acme Enterprise'
        assert res_put.json()['data']['base_currency'] == 'USD'

    def test_organization_deactivate_and_reactivate(self, api_client, saas_owner):
        org = saas_owner['org']
        tokens = saas_owner['tokens']
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        deactivate_url = reverse('organization-deactivate', kwargs={'organization_id': org.id})
        res_deact = api_client.post(deactivate_url)
        assert res_deact.status_code == status.HTTP_200_OK
        assert res_deact.json()['data']['is_active'] is False

        reactivate_url = reverse('organization-reactivate', kwargs={'organization_id': org.id})
        res_react = api_client.post(reactivate_url)
        assert res_react.status_code == status.HTTP_200_OK
        assert res_react.json()['data']['is_active'] is True

    def test_organization_delete(self, api_client, saas_owner):
        org = saas_owner['org']
        tokens = saas_owner['tokens']
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        url = reverse('organization-detail', kwargs={'organization_id': org.id})
        res = api_client.delete(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.json()['data']['deleted'] is True
        assert not Organization.objects.filter(id=org.id).exists()

    def test_superadmin_list_organizations(self, api_client, saas_owner):
        admin_user = User.objects.create_superuser(
            email="platform-superadmin@sbpafrica.group",
            password="AdminSuperPassword123!",
            first_name="Platform",
            last_name="Superadmin"
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        admin_token = str(RefreshToken.for_user(admin_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")

        url = reverse('organization-admin-list')
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert len(data) >= 1

    def test_inhouse_organization_never_expires_and_never_blocked(self, api_client, saas_owner):
        """
        Verify that an in-house organization (is_inhouse=True) is permanently exempt
        from subscription paywalls and never blocked with HTTP 402 even if plan_expires_at is in the past.
        """
        org = saas_owner['org']
        tokens = saas_owner['tokens']
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Mark organization as in-house
        org.is_inhouse = True
        org.plan = SubscriptionPlanTier.INHOUSE
        org.plan_expires_at = timezone.now() - datetime.timedelta(days=100)  # artificially past date
        org.save()

        assert org.is_subscription_active is True
        assert org.is_trial is False
        assert org.days_remaining == 99999

        # Request to financial domain endpoint works without 402
        res = api_client.get(f"/api/v1/ledger/public/accounts/?organization_id={org.id}")
        assert res.status_code == status.HTTP_200_OK

    def test_stakeholder_user_bypasses_subscription_lock(self, api_client, saas_owner):
        """
        Verify that internal stakeholders / board members / auditors can access and audit any organization
        (even an expired trial organization) without being blocked by HTTP 402.
        """
        org = saas_owner['org']
        org.is_inhouse = False
        org.plan = SubscriptionPlanTier.TRIAL
        org.plan_expires_at = timezone.now() - datetime.timedelta(days=5)  # Expired trial
        org.save()

        # Regular owner is blocked with 402
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {saas_owner['tokens']['access']}")
        res_blocked = api_client.get(f"/api/v1/ledger/public/accounts/?organization_id={org.id}")
        assert res_blocked.status_code == status.HTTP_402_PAYMENT_REQUIRED

        # Stakeholder user accesses the same expired tenant
        stakeholder = User.objects.create_user(
            email="stakeholder.auditor@sbpafrica.group",
            password="StakeholderPass123!",
            first_name="Board",
            last_name="Member",
            is_stakeholder=True
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        stakeholder_token = str(RefreshToken.for_user(stakeholder).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {stakeholder_token}")

        res_allowed = api_client.get(f"/api/v1/ledger/public/accounts/?organization_id={org.id}")
        assert res_allowed.status_code == status.HTTP_200_OK

    def test_customer_cannot_self_assign_inhouse_status(self, api_client, saas_owner):
        """
        Verify that normal customer tenant owners cannot self-assign is_inhouse=True (HTTP 403 Forbidden).
        Only Superadmins/Stakeholders can grant in-house exemption.
        """
        org = saas_owner['org']
        tokens = saas_owner['tokens']
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        url = reverse('organization-detail', kwargs={'organization_id': org.id})
        res = api_client.patch(url, {'is_inhouse': True}, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMultiTenantAdminIsolation:
    def test_organization_admin_sees_only_own_organization(self, rf):
        from django.contrib.admin.sites import AdminSite
        from apps.organizations.models import (
            Organization, SubscriptionPlan, SubscriptionPlanTier, OrganizationRole,
            OrganizationMembership, OrganizationInvitation, PaymentWebhookLog
        )
        from apps.organizations.admin import (
            OrganizationAdmin, OrganizationMembershipAdmin,
            SubscriptionTransactionAdmin, PaymentWebhookLogAdmin
        )
        from apps.users.admin import UserAdmin

        # Setup 2 separate organizations
        org_a = Organization.objects.create(name="Alpha Corp", slug="alpha-corp", plan=SubscriptionPlanTier.STARTER)
        admin_a = User.objects.create_user(
            email="admin@alpha.com",
            password="Password123!",
            first_name="Alpha",
            last_name="Admin",
            is_staff=True
        )
        OrganizationMembership.objects.create(organization=org_a, user=admin_a, role=OrganizationRole.ADMIN)

        org_b = Organization.objects.create(name="Beta Industries", slug="beta-ind", plan=SubscriptionPlanTier.GROWTH)
        admin_b = User.objects.create_user(
            email="admin@beta.com",
            password="Password123!",
            first_name="Beta",
            last_name="Admin",
            is_staff=True
        )
        OrganizationMembership.objects.create(organization=org_b, user=admin_b, role=OrganizationRole.ADMIN)

        superadmin = User.objects.create_superuser(
            email="super@sbpafrica.group",
            password="SuperPassword123!",
            first_name="Super",
            last_name="Admin"
        )

        site = AdminSite()
        org_admin = OrganizationAdmin(Organization, site)
        membership_admin = OrganizationMembershipAdmin(OrganizationMembership, site)
        user_admin = UserAdmin(User, site)
        webhook_admin = PaymentWebhookLogAdmin(PaymentWebhookLog, site)

        # 1. OrganizationAdmin isolation
        req_a = rf.get("/admin/organizations/organization/")
        req_a.user = admin_a
        qs_a = org_admin.get_queryset(req_a)
        assert list(qs_a) == [org_a]
        assert org_b not in qs_a

        req_b = rf.get("/admin/organizations/organization/")
        req_b.user = admin_b
        qs_b = org_admin.get_queryset(req_b)
        assert list(qs_b) == [org_b]
        assert org_a not in qs_b

        req_super = rf.get("/admin/organizations/organization/")
        req_super.user = superadmin
        qs_super = org_admin.get_queryset(req_super)
        assert org_a in qs_super
        assert org_b in qs_super

        # 2. Permissions: Non-superusers cannot add or delete organizations
        assert org_admin.has_add_permission(req_a) is False
        assert org_admin.has_delete_permission(req_a, obj=org_a) is False
        assert org_admin.has_add_permission(req_super) is True
        assert org_admin.has_delete_permission(req_super, obj=org_a) is True

        # 3. MembershipAdmin isolation
        m_qs_a = membership_admin.get_queryset(req_a)
        assert all(m.organization == org_a for m in m_qs_a)
        assert not any(m.organization == org_b for m in m_qs_a)

        # 4. UserAdmin isolation
        u_qs_a = user_admin.get_queryset(req_a)
        assert admin_a in u_qs_a
        assert admin_b not in u_qs_a

        # 5. Webhook logs hidden from non-superusers
        assert webhook_admin.has_module_permission(req_a) is False
        assert webhook_admin.has_module_permission(req_super) is True

    def test_api_tenant_isolation_and_header_anti_spoofing(self, api_client):
        """
        Verify that in the REST API backend:
        1. An admin of Organization A cannot access Organization B's detail endpoint (HTTP 403 Forbidden).
        2. If Admin A sends 'X-Organization-ID: <org_B_id>', TenantMiddleware rejects the spoofing
           and keeps the context bound strictly to Organization A.
        """
        org_a = Organization.objects.create(name="Alpha Corp", slug="alpha-corp", plan=SubscriptionPlanTier.GROWTH)
        admin_a = User.objects.create_user(
            email="admin_a@alpha.com",
            password="Password123!",
            first_name="Alpha",
            last_name="Admin"
        )
        OrganizationMembership.objects.create(organization=org_a, user=admin_a, role=OrganizationRole.ADMIN, is_default=True)

        org_b = Organization.objects.create(name="Beta Industries", slug="beta-ind", plan=SubscriptionPlanTier.GROWTH)
        admin_b = User.objects.create_user(
            email="admin_b@beta.com",
            password="Password123!",
            first_name="Beta",
            last_name="Admin"
        )
        OrganizationMembership.objects.create(organization=org_b, user=admin_b, role=OrganizationRole.ADMIN, is_default=True)

        # Authenticate as Admin A
        tokens_a = JWTTokenService.get_tokens_for_user(admin_a, org_a)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_a['access']}")

        # 1. Admin A can access Org A detail endpoint
        res_a = api_client.get(f"/api/v1/organizations/{org_a.id}/")
        assert res_a.status_code == status.HTTP_200_OK
        assert res_a.json()['data']['name'] == "Alpha Corp"

        # 2. Admin A CANNOT access Org B detail endpoint (HTTP 403 Forbidden)
        res_b = api_client.get(f"/api/v1/organizations/{org_b.id}/")
        assert res_b.status_code == status.HTTP_403_FORBIDDEN

        # 3. Admin A CANNOT access superadmin list of all organizations
        res_admin_list = api_client.get("/api/v1/organizations/admin/list/")
        assert res_admin_list.status_code == status.HTTP_403_FORBIDDEN

        # 4. Anti-spoofing: Admin A tries to pass Org B in 'X-Organization-ID' header
        # TenantMiddleware must reject Org B and keep the context as Org A
        res_spoof = api_client.get("/api/v1/organizations/billing/transactions/", HTTP_X_ORGANIZATION_ID=str(org_b.id))
        assert res_spoof.status_code == status.HTTP_200_OK
        # The returned response header must be Org A, NOT the spoofed Org B
        assert res_spoof.headers.get("X-Organization-ID") == str(org_a.id)






    def test_superadmin_create_organization_account_assigns_role(self, api_client, admin_user):
        """
        Tests that when superadmin creates an organizational account for someone,
        the user is assigned the ORGANIZATION_OWNER role and their role never shows as 'No Role'.
        """
        api_client.force_authenticate(user=admin_user)

        res = api_client.post("/api/v1/organizations/admin/create/", {
            "organization_name": "Tarkwa Mining Resources Ltd",
            "owner_email": "finance.director@tarkwamining.com",
            "owner_first_name": "Ebenezer",
            "owner_last_name": "Addae",
            "country_code": "GH",
            "base_currency": "GHS",
        }, format="json")

        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()["data"]
        assert data["name"] == "Tarkwa Mining Resources Ltd"

        # Verify User and Role in DB
        owner_user = User.objects.get(email="finance.director@tarkwamining.com")
        assert owner_user.role is not None
        assert owner_user.role.name == "ORGANIZATION_OWNER"
        assert owner_user.role_name == "ORGANIZATION_OWNER"
        assert "Organization Owner" in owner_user.get_role_display()
        assert owner_user.get_role_display() != "No Role"

        # Verify membership
        membership = OrganizationMembership.objects.get(user=owner_user)
        assert membership.role == OrganizationRole.OWNER
        assert membership.is_default is True

    def test_organization_membership_fallback_role_display(self):
        """
        Verifies that even if user.role is temporarily None, a user with an
        OrganizationMembership displays their organizational role instead of 'No Role'.
        """
        org = Organization.objects.create(name="Delta Mining Group", base_currency="GHS")
        user = User.objects.create_user(
            email="ops.manager@deltamining.com",
            first_name="Kwesi",
            last_name="Arthur",
            is_active=True
        )
        assert user.role is None

        # Link to organization as OWNER
        OrganizationMembership.objects.create(
            organization=org,
            user=user,
            role=OrganizationRole.OWNER,
            is_default=True
        )

        assert user.role_name == "OWNER"
        assert "Organization Owner" in user.get_role_display()
        assert user.get_role_display() != "No Role"
