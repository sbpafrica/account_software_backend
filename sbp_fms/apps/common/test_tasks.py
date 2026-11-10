import pytest
from unittest.mock import patch
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.core import mail

from apps.common.cache import CacheManager, make_cache_key
from apps.common.tasks import send_email_task, cleanup_expired_tokens_and_invitations_task
from apps.organizations.models import Organization, OrganizationInvitation, OrganizationRole
from apps.organizations.tasks import send_organization_invitation_email_task, send_welcome_onboarding_email_task
from apps.receivables.models import Client, ClientInvoice, ClientInvoiceStatus, PaymentReceipt
from apps.receivables.tasks import (
    send_invoice_email_task,
    send_payment_receipt_email_task,
    check_overdue_invoices_and_send_reminders_task
)
from apps.payables.models import Supplier, PaymentVoucher, PaymentVoucherStatus
from apps.payables.tasks import (
    send_payment_voucher_approval_alert_task,
    send_remittance_advice_email_task
)
from apps.assets.models import AssetCategory, FixedAsset, AssetStatus
from apps.assets.tasks import run_periodic_depreciation_batch_task
from apps.treasury.models import BankAccount, BankFeedConnection, BankFeedStatus
from apps.treasury.tasks import sync_active_bank_feeds_task
from apps.ledger.models import Account, AccountType
from apps.users.models import User, UserRole, Role


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="admin@sbpfms.com",
        password="Password123!",
        first_name="Admin",
        last_name="User"
    )


@pytest.fixture
def client_obj(db):
    return Client.objects.create(
        code="CL-TEST-001",
        name="Global Logistics Ltd",
        email="billing@globallogistics.com",
        country_code="GH"
    )


@pytest.fixture
def supplier_obj(db):
    return Supplier.objects.create(
        name="Tech Solutions Ltd",
        email="accounts@techsolutions.com",
        country_code="GH"
    )


@pytest.fixture
def bank_account_obj(db):
    gl = Account.objects.create(
        code="1020-TEST-BANK",
        name="GCB Operating Bank Account",
        account_type=AccountType.ASSET,
        currency="GHS",
        country_code="GH"
    )
    return BankAccount.objects.create(
        bank_name="GCB Bank",
        account_number="ACC-GH-12345",
        branch_name="High Street",
        swift_code="GCBLGHAC",
        currency="GHS",
        country_code="GH",
        gl_account=gl,
        is_active=True
    )


@pytest.mark.django_db
class TestCacheManagerAndTenantSeparation:
    def test_cache_set_get_and_invalidation(self):
        key = make_cache_key("fms:test:key", id="123")
        CacheManager.set(key, {"data": "cached_value"}, timeout=60)
        assert CacheManager.get(key) == {"data": "cached_value"}

        CacheManager.delete_pattern("fms:test:")
        assert CacheManager.get(key) is None

    def test_cache_multi_tenant_key_separation(self):
        from apps.organizations.context import set_current_organization, clear_current_organization

        org1 = Organization.objects.create(name="Tenant Alpha", base_currency="GHS")
        org2 = Organization.objects.create(name="Tenant Beta", base_currency="USD")

        set_current_organization(org1)
        key_org1 = make_cache_key("fms:accounts:list", country="GH")

        set_current_organization(org2)
        key_org2 = make_cache_key("fms:accounts:list", country="GH")

        clear_current_organization()

        assert str(org1.id) in key_org1
        assert str(org2.id) in key_org2
        assert key_org1 != key_org2


@pytest.mark.django_db
class TestBackgroundEmailTasks:
    def test_send_email_task(self):
        mail.outbox = []
        result = send_email_task(
            subject="Test Subject",
            recipient_list=["user@example.com"],
            message="Test email message body"
        )
        assert result is True
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Test Subject"
        assert mail.outbox[0].to == ["user@example.com"]

    def test_send_organization_invitation_email_task(self, superuser):
        mail.outbox = []
        org = Organization.objects.create(name="Apex Systems", base_currency="GHS")
        inv = OrganizationInvitation.objects.create(
            organization=org,
            email="invitee@apex.com",
            role=OrganizationRole.ACCOUNTANT,
            invited_by=superuser,
            expires_at=timezone.now() + timedelta(days=7)
        )
        res = send_organization_invitation_email_task(str(inv.id))
        assert res is True
        assert len(mail.outbox) == 1
        assert "invited you to join 'Apex Systems'" in mail.outbox[0].body
        assert str(inv.token) in mail.outbox[0].body

    def test_send_welcome_onboarding_email_task(self, superuser):
        mail.outbox = []
        org = Organization.objects.create(name="Apex Systems", base_currency="GHS")
        res = send_welcome_onboarding_email_task(str(org.id), str(superuser.id))
        assert res is True
        assert len(mail.outbox) == 1
        assert "Welcome to SBP-FMS" in mail.outbox[0].subject

    def test_send_invoice_email_task(self, client_obj):
        mail.outbox = []
        inv = ClientInvoice.objects.create(
            invoice_number="INV-2026-001",
            client=client_obj,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('150.00'),
            total_amount=Decimal('1150.00')
        )
        res = send_invoice_email_task(str(inv.id))
        assert res is True
        assert len(mail.outbox) == 1
        assert "Invoice INV-2026-001" in mail.outbox[0].subject
        assert "1,150.00" in mail.outbox[0].body

    def test_send_payment_receipt_email_task(self, client_obj, bank_account_obj):
        mail.outbox = []
        receipt = PaymentReceipt.objects.create(
            receipt_number="REC-2026-001",
            client=client_obj,
            bank_account=bank_account_obj,
            receipt_date=timezone.now().date(),
            amount_received=Decimal('500.00'),
            payment_method="BANK_TRANSFER"
        )
        res = send_payment_receipt_email_task(str(receipt.id))
        assert res is True
        assert len(mail.outbox) == 1
        assert "Payment Receipt REC-2026-001" in mail.outbox[0].subject

    def test_send_payment_voucher_approval_alert_task(self, superuser, supplier_obj, bank_account_obj):
        mail.outbox = []
        role_sa, _ = Role.objects.get_or_create(name=UserRole.SUPER_ADMIN)
        superuser.role = role_sa
        superuser.save(update_fields=['role'])

        preparer = User.objects.create_user(
            email="clerk@sbpfms.com",
            password="Password123!",
            first_name="Finance",
            last_name="Clerk"
        )

        voucher = PaymentVoucher.objects.create(
            voucher_number="PV-2026-001",
            voucher_date=timezone.now().date(),
            payee_name=supplier_obj.name,
            supplier=supplier_obj,
            prepared_by=preparer,
            bank_account=bank_account_obj,
            gross_amount=Decimal('2500.00'),
            net_amount=Decimal('2500.00'),
            description="Office Supplies",
            status=PaymentVoucherStatus.SUBMITTED
        )
        res = send_payment_voucher_approval_alert_task(str(voucher.id))
        assert res is True
        assert len(mail.outbox) == 1
        assert "ACTION REQUIRED: Payment Voucher PV-2026-001" in mail.outbox[0].subject

    def test_send_remittance_advice_email_task(self, superuser, supplier_obj, bank_account_obj):
        mail.outbox = []
        voucher = PaymentVoucher.objects.create(
            voucher_number="PV-2026-002",
            voucher_date=timezone.now().date(),
            payee_name=supplier_obj.name,
            supplier=supplier_obj,
            prepared_by=superuser,
            bank_account=bank_account_obj,
            gross_amount=Decimal('3000.00'),
            net_amount=Decimal('3000.00'),
            description="IT Consulting Services",
            status=PaymentVoucherStatus.PAID
        )
        res = send_remittance_advice_email_task(str(voucher.id))
        assert res is True
        assert len(mail.outbox) == 1
        assert "Remittance Advice: Payment PV-2026-002" in mail.outbox[0].subject


@pytest.mark.django_db
class TestPeriodicBackgroundTasks:
    def test_cleanup_expired_tokens_and_invitations_task(self, superuser):
        org = Organization.objects.create(name="Stale Org", base_currency="GHS")
        OrganizationInvitation.objects.create(
            organization=org,
            email="old@stale.com",
            role=OrganizationRole.MEMBER,
            invited_by=superuser,
            expires_at=timezone.now() - timedelta(days=2)
        )
        OrganizationInvitation.objects.create(
            organization=org,
            email="active@stale.com",
            role=OrganizationRole.MEMBER,
            invited_by=superuser,
            expires_at=timezone.now() + timedelta(days=5)
        )
        res = cleanup_expired_tokens_and_invitations_task()
        assert res['purged_invitations_count'] == 1
        assert OrganizationInvitation.objects.filter(email="active@stale.com").exists()
        assert not OrganizationInvitation.objects.filter(email="old@stale.com").exists()

    def test_check_overdue_invoices_and_send_reminders_task(self, client_obj):
        mail.outbox = []
        inv = ClientInvoice.objects.create(
            invoice_number="INV-OVERDUE-01",
            client=client_obj,
            issue_date=timezone.now().date() - timedelta(days=45),
            due_date=timezone.now().date() - timedelta(days=15),
            subtotal=Decimal('5000.00'),
            total_amount=Decimal('5000.00'),
            amount_paid=Decimal('0.00'),
            status=ClientInvoiceStatus.ISSUED
        )
        res = check_overdue_invoices_and_send_reminders_task()
        assert res['marked_overdue_count'] >= 1
        assert res['reminders_dispatched_count'] >= 1

        inv.refresh_from_db()
        assert inv.status == ClientInvoiceStatus.OVERDUE
        assert len(mail.outbox) >= 1
        assert "OVERDUE PAYMENT REMINDER" in mail.outbox[0].subject

    def test_sync_active_bank_feeds_task(self, bank_account_obj):
        conn = BankFeedConnection.objects.create(
            bank_account=bank_account_obj,
            provider="GCB",
            status=BankFeedStatus.CONNECTED
        )
        with patch('apps.treasury.bank_feed.BankFeedService.sync_live_feed') as mock_sync:
            mock_sync.return_value = {'success': True}
            res = sync_active_bank_feeds_task()
            assert res['synced_count'] == 1
            mock_sync.assert_called_once()
