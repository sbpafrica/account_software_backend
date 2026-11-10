import pytest
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
