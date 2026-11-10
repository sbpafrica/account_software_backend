import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from apps.common.models import BaseModel


class BillingInterval(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Monthly'
    ANNUALLY = 'ANNUALLY', 'Annually'
    ONETIME = 'ONETIME', 'One-Time'
    FREE = 'FREE', 'Free'


class SubscriptionPlanTier(models.TextChoices):
    TRIAL = 'TRIAL', '14-Day Free Trial'
    STARTER = 'STARTER', 'Starter Tier (Single Entity)'
    GROWTH = 'GROWTH', 'Growth Tier (Multi-Entity / Multi-Currency)'
    ENTERPRISE = 'ENTERPRISE', 'Enterprise Tier (Unlimited Subsidiaries & Custom Rules)'
    CUSTOM = 'CUSTOM', 'Custom Dynamic Plan'


class SubscriptionPlan(BaseModel):
    """
    [DYNAMIC SAAS SUBSCRIPTION PLAN]:
    Superadmin-configured subscription plan stored dynamically in the database.
    Can be synchronized with Paystack via Paystack Plan API (/plan).
    Defines tier limits, feature gating, billing interval, and pricing.
    """
    name = models.CharField(max_length=150, help_text="Plan display name, e.g. Growth Monthly, Enterprise Annual")
    code = models.SlugField(max_length=100, unique=True, help_text="Unique slug code identifier, e.g. growth-monthly")
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Price in plan currency")
    currency = models.CharField(max_length=3, default='GHS', help_text="Billing currency (e.g. GHS, USD, NGN)")
    interval = models.CharField(max_length=20, choices=BillingInterval.choices, default=BillingInterval.MONTHLY)
    paystack_plan_code = models.CharField(max_length=100, blank=True, default='', help_text="Paystack Plan Code (e.g. PLN_xxxx) synced with Paystack")
    trial_period_days = models.PositiveIntegerField(default=0, help_text="Number of free trial days (0 for no trial)")
    max_users = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum allowed active users (null for unlimited)")
    max_subsidiaries = models.PositiveIntegerField(default=1, help_text="Maximum allowed subsidiaries / entities")
    features = models.JSONField(default=list, blank=True, help_text="List of feature codes or capability descriptions included")
    is_active = models.BooleanField(default=True, db_index=True)
    is_public = models.BooleanField(default=True, help_text="Whether visible to customers on pricing page / signup")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['price', 'name']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.currency} {self.price}/{self.interval}"


class Organization(BaseModel):
    """
    [SAAS TENANT ROOT ENTITY]:
    Top-level organizational tenant in SBP-FMS.
    Represents an independent client company operating on the platform.
    Can own multiple subsidiaries/country entities, bank feeds, and team members.
    """
    name = models.CharField(max_length=200, help_text="Legal or trading entity name of customer organization.")
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    subdomain = models.SlugField(max_length=63, unique=True, null=True, blank=True, db_index=True)
    plan = models.CharField(max_length=50, choices=SubscriptionPlanTier.choices, default=SubscriptionPlanTier.TRIAL)
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='organizations',
        help_text="Linked dynamic subscription plan created by Superadmin."
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    paystack_customer_code = models.CharField(max_length=100, blank=True, default='', help_text="Paystack Customer Code (e.g. CUS_xxxx)")
    paystack_subscription_code = models.CharField(max_length=100, blank=True, default='', help_text="Paystack Subscription Code (e.g. SUB_xxxx)")
    base_currency = models.CharField(max_length=3, default='GHS', help_text="Default base reporting currency (e.g. GHS, USD, NGN, KES).")
    is_active = models.BooleanField(default=True, db_index=True)
    billing_email = models.EmailField(blank=True, default='')
    settings = models.JSONField(default=dict, blank=True, help_text="Tenant-specific customizations, feature flags, and UI branding.")

    class Meta:
        ordering = ['name']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return f"{self.name} ({self.slug}) - [{self.plan}]"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'org'
            candidate = base_slug
            counter = 1
            while Organization.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class OrganizationRole(models.TextChoices):
    OWNER = 'OWNER', 'Organization Owner (Full Billing & Management Control)'
    ADMIN = 'ADMIN', 'Organization Admin (Users, Settings & Approvals)'
    ACCOUNTANT = 'ACCOUNTANT', 'Senior Accountant (Journals, Ledgers, Approvals)'
    CLERK = 'CLERK', 'Finance Clerk (Data Entry, Invoicing, Vouchers)'
    AUDITOR = 'AUDITOR', 'Auditor (Strictly Read-Only Access)'
    MEMBER = 'MEMBER', 'Standard Member'


class OrganizationMembership(BaseModel):
    """
    Connects a User to an Organization with a specific tenant-level role.
    Supports outsourced accountants or fractional CFOs belonging to multiple customer organizations.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    role = models.CharField(
        max_length=30,
        choices=OrganizationRole.choices,
        default=OrganizationRole.MEMBER
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Designates this organization as the user's primary active tenant upon login."
    )

    class Meta:
        unique_together = ('organization', 'user')
        ordering = ['-is_default', 'organization__name']

    def __str__(self):
        return f"{self.user.email} in {self.organization.name} as {self.role}"


class OrganizationInvitation(BaseModel):
    """
    Pending invitations for new team members to join an organization.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=30, choices=OrganizationRole.choices, default=OrganizationRole.MEMBER)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+'
    )
    accepted = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite for {self.email} to {self.organization.name} ({self.role})"


class TransactionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Payment'
    SUCCESS = 'SUCCESS', 'Successful'
    FAILED = 'FAILED', 'Failed'
    ABANDONED = 'ABANDONED', 'Abandoned'


class SubscriptionTransaction(BaseModel):
    """
    [SUBSCRIPTION TRANSACTION LOG]:
    Tracks payment checkouts, Paystack references, amounts, and statuses.
    Includes Idempotency key tracking to guarantee idempotent execution.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='subscription_transactions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='GHS')
    reference = models.CharField(max_length=120, unique=True, db_index=True, help_text="Unique transaction reference sent to Paystack")
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING, db_index=True)
    channel = models.CharField(max_length=50, blank=True, default='', help_text="Payment channel (card, mobile_money, bank, etc.)")
    paid_at = models.DateTimeField(null=True, blank=True)
    paystack_response = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True, help_text="Client idempotency key header value")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        return f"Tx {self.reference} - {self.organization.name} - {self.currency} {self.amount} [{self.status}]"


class PaymentWebhookLog(BaseModel):
    """
    [PAYMENT GATEWAY WEBHOOK AUDIT LOG]:
    Guarantees strict once-and-only-once webhook processing.
    Records raw payload and processing status. Replayed or duplicate webhooks
    with matching event_id are immediately identified and ignored safely.
    """
    provider = models.CharField(max_length=50, default='PAYSTACK', db_index=True)
    event_id = models.CharField(max_length=150, unique=True, db_index=True, help_text="Unique webhook event ID or hash")
    event_type = models.CharField(max_length=100, db_index=True, help_text="Event name, e.g. charge.success, subscription.create")
    reference = models.CharField(max_length=150, blank=True, default='', db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider} [{self.event_type}] - {self.event_id} (Processed: {self.processed})"

