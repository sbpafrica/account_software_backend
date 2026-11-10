import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User, Role, UserRole
from apps.organizations.models import (
    Organization, SubscriptionPlan, BillingInterval,
    SubscriptionTransaction, TransactionStatus, PaymentWebhookLog,
    OrganizationRole, OrganizationMembership
)
from apps.organizations.services import OrganizationService, SubscriptionPlanService, BillingService
from apps.common.models import IdempotencyRecord


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def superuser(db):
    user = User.objects.create_superuser(
        email="superadmin@sbp.com",
        password="SuperPassword123!",
        first_name="Platform",
        last_name="SuperAdmin"
    )
    role, _ = Role.objects.get_or_create(name=UserRole.SUPER_ADMIN, defaults={'description': 'Super Admin'})
    user.role = role
    user.save()
    return user


@pytest.fixture
def tenant_owner(db):
    org, user, tokens = OrganizationService.register_customer(
        organization_name="Apex Global Holdings",
        email="apex.owner@apex.com",
        password="SecureOwnerPassword123!",
        first_name="Arthur",
        last_name="Apex",
        country_code="GH",
        base_currency="GHS"
    )
    return {
        'org': org,
        'user': user,
        'tokens': tokens
    }


@pytest.fixture
def standard_plan(db, superuser):
    return SubscriptionPlanService.create_plan(
        name="Growth Tier",
        price=Decimal("250.00"),
        interval=BillingInterval.MONTHLY,
        currency="GHS",
        code="growth-monthly",
        description="Ideal for growing regional multi-entity companies",
        max_users=15,
        max_subsidiaries=3,
        features=["MULTI_CURRENCY", "BANK_FEEDS", "CONSOLIDATION"],
        sync_paystack=False,
        user=superuser
    )


@pytest.mark.django_db
class TestSubscriptionPlanManagement:
    """
    Tests Superadmin dynamic plan creation, update, and public catalog visibility.
    """

    def test_superadmin_create_dynamic_plan_via_api(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)
        url = reverse('billing-plans-admin-list-create')
        payload = {
            'name': 'Enterprise Ultra',
            'code': 'enterprise-ultra',
            'price': '999.00',
            'currency': 'USD',
            'interval': 'ANNUALLY',
            'max_users': 50,
            'max_subsidiaries': 10,
            'features': ['FULL_ERP', 'CUSTOM_INTEGRATIONS', 'PRIORITY_SUPPORT'],
            'sync_paystack': False
        }

        resp = api_client.post(url, data=payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['data']['name'] == 'Enterprise Ultra'
        assert resp.data['data']['code'] == 'enterprise-ultra'
        assert resp.data['data']['currency'] == 'USD'
        assert Decimal(resp.data['data']['price']) == Decimal('999.00')

        # Verify persisted in database
        plan = SubscriptionPlan.objects.get(code='enterprise-ultra')
        assert plan.max_users == 50
        assert plan.max_subsidiaries == 10

    def test_non_admin_cannot_create_plan(self, api_client, tenant_owner):
        api_client.force_authenticate(user=tenant_owner['user'])
        url = reverse('billing-plans-admin-list-create')
        resp = api_client.post(url, data={'name': 'Hacker Plan', 'price': '1.00'}, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_public_plans_list(self, api_client, standard_plan):
        url = reverse('billing-plans-public-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data['data']
        assert len(data) >= 1
        plan_names = [p['name'] for p in data]
        assert 'Growth Tier' in plan_names


@pytest.mark.django_db
class TestPaystackBillingAndIdempotency:
    """
    Tests Paystack checkout initialization, transaction verification, and header-driven idempotency.
    """

    @patch('apps.organizations.paystack.PaystackService.initialize_transaction')
    def test_initialize_checkout_success_and_idempotency(self, mock_init, api_client, tenant_owner, standard_plan):
        mock_init.return_value = {
            'authorization_url': 'https://checkout.paystack.com/auth_code_123',
            'access_code': 'auth_code_123',
            'reference': 'test_ref_001'
        }

        api_client.force_authenticate(user=tenant_owner['user'])
        url = reverse('billing-initialize')
        payload = {
            'plan_id': str(standard_plan.id),
            'callback_url': 'https://app.sbpfms.com/billing/callback'
        }
        idempotency_key = "idemp-key-checkout-9999"

        # 1. First execution
        resp1 = api_client.post(
            url,
            data=payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        assert resp1.status_code == status.HTTP_201_CREATED
        assert resp1.data['data']['authorization_url'] == 'https://checkout.paystack.com/auth_code_123'
        assert mock_init.call_count == 1

        # 2. Duplicate execution with identical Idempotency-Key
        resp2 = api_client.post(
            url,
            data=payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        assert resp2.status_code == status.HTTP_201_CREATED
        assert resp2.headers.get('X-Idempotency-Replay') == 'true'
        # Crucial check: external payment gateway was NOT invoked a second time
        assert mock_init.call_count == 1

    @patch('apps.organizations.paystack.PaystackService.verify_transaction')
    def test_verify_transaction_and_activate_subscription(self, mock_verify, api_client, tenant_owner, standard_plan):
        org = tenant_owner['org']
        tx = SubscriptionTransaction.objects.create(
            organization=org,
            plan=standard_plan,
            amount=standard_plan.price,
            currency=standard_plan.currency,
            reference="ref_verify_test_123",
            status=TransactionStatus.PENDING
        )

        mock_verify.return_value = {
            'status': 'success',
            'reference': 'ref_verify_test_123',
            'amount': 25000,
            'currency': 'GHS',
            'channel': 'card',
            'paid_at': '2026-11-10T15:00:00.000Z',
            'customer': {'customer_code': 'CUS_mock_123'},
            'subscription': {'subscription_code': 'SUB_mock_456'}
        }

        api_client.force_authenticate(user=tenant_owner['user'])
        url = reverse('billing-verify')
        resp = api_client.post(url, data={'reference': 'ref_verify_test_123'}, format='json')

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['data']['status'] == TransactionStatus.SUCCESS

        # Verify database mutation
        tx.refresh_from_db()
        org.refresh_from_db()
        assert tx.status == TransactionStatus.SUCCESS
        assert tx.channel == 'card'
        assert org.subscription_plan == standard_plan
        assert org.plan == standard_plan.code
        assert org.paystack_customer_code == 'CUS_mock_123'
        assert org.paystack_subscription_code == 'SUB_mock_456'
        assert org.plan_expires_at is not None

        # Re-verify is completely idempotent and doesn't crash or re-bill
        resp_again = api_client.post(url, data={'reference': 'ref_verify_test_123'}, format='json')
        assert resp_again.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestPaystackWebhookProcessing:
    """
    Tests secure HMAC-SHA512 webhook ingestion and deduplication via PaymentWebhookLog.
    """

    @patch('apps.organizations.paystack.PaystackService.verify_transaction')
    def test_paystack_webhook_charge_success_and_deduplication(self, mock_verify, api_client, tenant_owner, standard_plan):
        org = tenant_owner['org']
        tx = SubscriptionTransaction.objects.create(
            organization=org,
            plan=standard_plan,
            amount=standard_plan.price,
            currency=standard_plan.currency,
            reference="ref_webhook_test_888",
            status=TransactionStatus.PENDING
        )

        mock_verify.return_value = {
            'status': 'success',
            'reference': 'ref_webhook_test_888',
            'amount': 25000,
            'channel': 'mobile_money',
            'paid_at': '2026-11-10T15:00:00.000Z',
        }

        webhook_payload = {
            'event': 'charge.success',
            'data': {
                'id': 12345678,
                'reference': 'ref_webhook_test_888',
                'amount': 25000,
                'currency': 'GHS',
                'status': 'success',
                'channel': 'mobile_money'
            }
        }
        body_bytes = json.dumps(webhook_payload).encode('utf-8')
        secret_key = 'sk_test_mock_paystack_secret_key'

        # Generate HMAC-SHA512 signature
        valid_signature = hmac.new(
            secret_key.encode('utf-8'),
            body_bytes,
            hashlib.sha512
        ).hexdigest()

        url = reverse('billing-paystack-webhook')

        # 1. First webhook post
        resp1 = api_client.post(
            url,
            data=body_bytes,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=valid_signature
        )
        assert resp1.status_code == status.HTTP_200_OK
        assert resp1.data['data']['status'] == 'success'

        # Verify transaction and organization status
        tx.refresh_from_db()
        org.refresh_from_db()
        assert tx.status == TransactionStatus.SUCCESS
        assert org.subscription_plan == standard_plan

        # Verify webhook audit log
        log_entry = PaymentWebhookLog.objects.filter(reference='ref_webhook_test_888').first()
        assert log_entry is not None
        assert log_entry.processed is True

        # 2. Duplicate webhook replay (e.g. Paystack network retries)
        resp2 = api_client.post(
            url,
            data=body_bytes,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=valid_signature
        )
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.data['data']['status'] == 'ignored'
        assert 'already been processed' in resp2.data['data']['message']

    def test_paystack_webhook_invalid_signature_rejected(self, api_client):
        url = reverse('billing-paystack-webhook')
        payload = {'event': 'charge.success', 'data': {'reference': 'fake_ref'}}
        body_bytes = json.dumps(payload).encode('utf-8')

        resp = api_client.post(
            url,
            data=body_bytes,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='invalid_bogus_signature_hash'
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'signature' in resp.data['message'].lower()
