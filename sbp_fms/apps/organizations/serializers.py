from rest_framework import serializers
from apps.users.serializers import UserOutputSerializer
from apps.organizations.models import (
    Organization, SubscriptionPlan, SubscriptionPlanTier, BillingInterval,
    TransactionStatus, SubscriptionTransaction, PaymentWebhookLog,
    OrganizationRole, OrganizationMembership, OrganizationInvitation
)


class SubscriptionPlanOutputSerializer(serializers.ModelSerializer):
    """
    Output representation of a SaaS subscription plan configured dynamically by Superadmin.
    """
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'code', 'description', 'price',
            'currency', 'interval', 'paystack_plan_code',
            'trial_period_days', 'max_users', 'max_subsidiaries',
            'features', 'is_active', 'is_public',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class SubscriptionPlanInputSerializer(serializers.Serializer):
    """
    Input payload for Superadmin creating or updating a dynamic subscription plan.
    """
    name = serializers.CharField(max_length=150, help_text="Plan display name (e.g. Growth Tier Monthly)")
    code = serializers.SlugField(max_length=100, required=False, help_text="Optional unique slug code. Generated if omitted.")
    description = serializers.CharField(required=False, allow_blank=True, default='')
    price = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Price in plan currency (e.g. 150.00)")
    currency = serializers.CharField(max_length=3, default='GHS', required=False, help_text="Three-letter currency code (GHS, USD, NGN)")
    interval = serializers.ChoiceField(
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
        required=False,
        help_text="Billing recurrence interval (MONTHLY, ANNUALLY, ONETIME, FREE)"
    )
    trial_period_days = serializers.IntegerField(default=0, min_value=0, required=False, help_text="Trial days granted upon selection")
    max_users = serializers.IntegerField(required=False, allow_null=True, min_value=1, help_text="Max team members allowed (null for unlimited)")
    max_subsidiaries = serializers.IntegerField(default=1, min_value=1, required=False, help_text="Max legal subsidiary entities allowed")
    features = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        required=False,
        help_text="List of feature codes or capabilities included"
    )
    is_active = serializers.BooleanField(default=True, required=False)
    is_public = serializers.BooleanField(default=True, required=False, help_text="Whether visible to public customers on pricing page")
    sync_paystack = serializers.BooleanField(default=True, required=False, help_text="Sync plan creation with Paystack Plan API")


class OrganizationOutputSerializer(serializers.ModelSerializer):
    """
    Detailed output representation of an Organization tenant.
    """
    subscription_plan = SubscriptionPlanOutputSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'subdomain',
            'plan', 'subscription_plan', 'plan_expires_at', 'base_currency',
            'paystack_customer_code', 'paystack_subscription_code',
            'is_active', 'billing_email', 'settings',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class OrganizationMembershipOutputSerializer(serializers.ModelSerializer):
    """
    Output representation of a user's membership within an organization.
    """
    organization = OrganizationOutputSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            'id', 'organization', 'role',
            'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class OrganizationRegisterInputSerializer(serializers.Serializer):
    """
    Input payload for public self-service customer registration.
    """
    organization_name = serializers.CharField(
        max_length=200,
        help_text="Official business or corporate trading entity name."
    )
    email = serializers.EmailField(
        help_text="Owner/administrator corporate email address for platform authentication."
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text="Secure password for the administrator account (min 8 characters)."
    )
    first_name = serializers.CharField(max_length=150, help_text="Administrator first name.")
    last_name = serializers.CharField(max_length=150, help_text="Administrator last name.")
    country_code = serializers.CharField(
        max_length=2,
        default='GH',
        required=False,
        help_text="Two-letter ISO country code of headquarters (e.g. GH, NG, KE, ZA)."
    )
    base_currency = serializers.CharField(
        max_length=3,
        default='GHS',
        required=False,
        help_text="Primary financial accounting reporting currency (e.g. GHS, USD, NGN, KES, EUR)."
    )
    subdomain = serializers.SlugField(
        max_length=63,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional dedicated workspace subdomain (e.g. acme for acme.sbpfms.com)."
    )
    plan = serializers.CharField(
        max_length=50,
        default=SubscriptionPlanTier.TRIAL,
        required=False,
        help_text="Initial SaaS subscription plan code or tier."
    )


class OrganizationRegisterOutputSerializer(serializers.Serializer):
    """
    Response returned upon successful SaaS registration.
    """
    organization = OrganizationOutputSerializer()
    user = UserOutputSerializer()
    access = serializers.CharField(help_text="JWT Bearer access token scoped to the created organization.")
    refresh = serializers.CharField(help_text="JWT refresh token.")


class OrganizationSwitchInputSerializer(serializers.Serializer):
    """
    Payload to switch active tenant context.
    """
    organization_id = serializers.UUIDField(
        help_text="UUID of the target organization to switch into."
    )


class OrganizationSwitchOutputSerializer(serializers.Serializer):
    """
    Response with refreshed JWT tokens for the switched organization.
    """
    access = serializers.CharField(help_text="New JWT Bearer access token scoped to the switched organization.")
    refresh = serializers.CharField(help_text="New JWT refresh token.")
    organization = OrganizationOutputSerializer()
    role = serializers.CharField(help_text="Role of the user in the selected organization.")


class OrganizationInviteInputSerializer(serializers.Serializer):
    """
    Payload for inviting team members to an organization.
    """
    organization_id = serializers.UUIDField(help_text="Target organization UUID.")
    email = serializers.EmailField(help_text="Email of colleague to invite.")
    role = serializers.ChoiceField(
        choices=OrganizationRole.choices,
        default=OrganizationRole.MEMBER,
        help_text="Designated organizational role."
    )


class OrganizationInvitationOutputSerializer(serializers.ModelSerializer):
    """
    Output representation of an invitation.
    """
    class Meta:
        model = OrganizationInvitation
        fields = [
            'id', 'organization_id', 'email', 'role',
            'token', 'expires_at', 'accepted', 'created_at'
        ]
        read_only_fields = fields


class OrganizationAcceptInviteInputSerializer(serializers.Serializer):
    """
    Payload to accept a team invitation.
    """
    token = serializers.UUIDField(help_text="Unique invitation UUID token received via invite.")


class OrganizationUpdateInputSerializer(serializers.Serializer):
    """
    Payload for updating organization settings and branding.
    """
    name = serializers.CharField(max_length=200, required=False)
    base_currency = serializers.CharField(max_length=3, required=False)
    billing_email = serializers.EmailField(required=False)
    settings = serializers.DictField(required=False, help_text="Tenant-specific customizations and UI branding.")


class BillingInitializeInputSerializer(serializers.Serializer):
    """
    Input payload to initialize a Paystack subscription checkout for the active organization.
    """
    plan_id = serializers.UUIDField(help_text="UUID of the SubscriptionPlan to subscribe to.")
    callback_url = serializers.URLField(required=False, allow_null=True, help_text="Frontend redirection URL after Paystack checkout completion.")


class BillingInitializeOutputSerializer(serializers.Serializer):
    """
    Paystack authorization redirect and checkout reference details.
    """
    authorization_url = serializers.URLField(help_text="Paystack secure checkout URL to redirect the user to.")
    access_code = serializers.CharField(help_text="Paystack checkout access code.")
    reference = serializers.CharField(help_text="Unique transaction reference for tracking and verification.")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in billing currency.")
    currency = serializers.CharField(max_length=3, help_text="Three-letter currency code (e.g. GHS).")


class BillingVerifyInputSerializer(serializers.Serializer):
    """
    Input payload to manually or synchronously verify a Paystack checkout transaction.
    """
    reference = serializers.CharField(help_text="Paystack transaction reference received upon checkout completion.")


class SubscriptionTransactionOutputSerializer(serializers.ModelSerializer):
    """
    Detailed output representation of a subscription payment transaction.
    """
    plan = SubscriptionPlanOutputSerializer(read_only=True)

    class Meta:
        model = SubscriptionTransaction
        fields = [
            'id', 'reference', 'amount', 'currency', 'status',
            'channel', 'paid_at', 'plan', 'created_at'
        ]
        read_only_fields = fields


class BillingVerifyOutputSerializer(serializers.Serializer):
    """
    Response detailing verification result and activated subscription.
    """
    status = serializers.ChoiceField(choices=TransactionStatus.choices)
    message = serializers.CharField()
    transaction = SubscriptionTransactionOutputSerializer(allow_null=True)
    organization = OrganizationOutputSerializer()


class PaystackWebhookInputSerializer(serializers.Serializer):
    """
    Paystack webhook payload structure.
    """
    event = serializers.CharField(help_text="Event type name, e.g. charge.success, subscription.create")
    data = serializers.DictField(help_text="Event object details containing transaction reference, customer, etc.")

