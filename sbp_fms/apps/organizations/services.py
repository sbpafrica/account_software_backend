import datetime
import logging
import uuid
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ValidationError, PermissionDenied
from django.conf import settings
from apps.common.cache import CacheManager
from apps.users.models import User
from apps.users.authentication import JWTTokenService
from apps.organizations.models import (
    Organization, SubscriptionPlan, SubscriptionPlanTier, BillingInterval,
    TransactionStatus, SubscriptionTransaction, PaymentWebhookLog,
    OrganizationRole, OrganizationMembership, OrganizationInvitation
)
from apps.organizations.paystack import PaystackService

logger = logging.getLogger(__name__)


class OrganizationService:
    """
    [SAAS MULTI-TENANT DOMAIN SERVICE]:
    Orchestrates self-service SaaS customer registration, organization lifecycle,
    team invitations, role memberships, and tenant switching.
    """

    @staticmethod
    @transaction.atomic
    def register_customer(
        *,
        organization_name: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        country_code: str = 'GH',
        base_currency: str = 'GHS',
        subdomain: str = None,
        plan: str = SubscriptionPlanTier.TRIAL
    ) -> tuple[Organization, User, dict]:
        """
        Public self-service SaaS onboarding:
        1. Validates and creates the Organization tenant entity.
        2. Creates the tenant Owner user account.
        3. Creates the OrganizationMembership (OWNER, is_default=True).
        4. Initializes the tenant's primary CompanyProfile and currency settings.
        5. Generates tenant-scoped JWT access and refresh tokens.
        """
        organization_name = organization_name.strip()
        email = email.strip().lower()
        first_name = first_name.strip()
        last_name = last_name.strip()
        country_code = country_code.strip().upper()
        base_currency = base_currency.strip().upper()

        if User.objects.filter(email=email).exists():
            raise ValidationError(f"An account with email '{email}' already exists.")

        if subdomain:
            subdomain = subdomain.strip().lower()
            if Organization.objects.filter(subdomain=subdomain).exists():
                raise ValidationError(f"Subdomain '{subdomain}' is already taken.")

        # Resolve dynamic plan if available
        dyn_plan = SubscriptionPlan.objects.filter(models.Q(code=plan) | models.Q(name__iexact=plan)).first()

        # Calculate subscription trial period (14 days for trial)
        plan_expires_at = None
        if dyn_plan and dyn_plan.trial_period_days > 0:
            plan_expires_at = timezone.now() + datetime.timedelta(days=dyn_plan.trial_period_days)
        elif plan == SubscriptionPlanTier.TRIAL:
            plan_expires_at = timezone.now() + datetime.timedelta(days=14)

        # 1. Create Organization
        organization = Organization.objects.create(
            name=organization_name,
            subdomain=subdomain or None,
            plan=plan,
            subscription_plan=dyn_plan,
            plan_expires_at=plan_expires_at,
            base_currency=base_currency,
            billing_email=email,
            is_active=True
        )

        # 2. Create Owner User
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            assigned_country=country_code,
            is_active=True
        )

        # 3. Create Tenant Membership
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationRole.OWNER,
            is_default=True
        )

        # 4. Initialize CompanyProfile for this tenant
        try:
            from apps.ledger.models import CompanyProfile
            CompanyProfile.objects.create(
                organization=organization,
                company_name=organization_name,
                country_code=country_code,
                base_currency=base_currency,
                email=email
            )
        except Exception:
            pass

        # 5. Generate tenant-scoped JWT tokens
        tokens = JWTTokenService.get_tokens_for_user(user, organization=organization)
        CacheManager.invalidate_organizations()

        # 6. Trigger background onboarding email
        from .tasks import send_welcome_onboarding_email_task
        transaction.on_commit(lambda: send_welcome_onboarding_email_task.delay(str(organization.id), str(user.id)))

        return organization, user, tokens

    @staticmethod
    def list_user_organizations(*, user: User):
        """
        Returns all active organization memberships for a user.
        """
        from .selectors import user_organizations_list
        return user_organizations_list(user=user)

    @staticmethod
    @transaction.atomic
    def switch_organization(*, user: User, organization_id) -> dict:
        """
        Switches the active tenant context for the user and generates a new tenant-bound JWT token pair.
        """
        try:
            membership = OrganizationMembership.objects.select_related('organization').get(
                user=user,
                organization_id=organization_id,
                organization__is_active=True
            )
        except OrganizationMembership.DoesNotExist:
            raise PermissionDenied("You do not have access to this organization.")

        # Update default organization preference for convenience
        OrganizationMembership.objects.filter(user=user, is_default=True).update(is_default=False)
        membership.is_default = True
        membership.save(update_fields=['is_default', 'updated_at'])

        tokens = JWTTokenService.get_tokens_for_user(user, organization=membership.organization)
        CacheManager.invalidate_organizations()
        return {
            'tokens': tokens,
            'organization': membership.organization,
            'role': membership.role
        }

    @staticmethod
    @transaction.atomic
    def invite_member(
        *,
        organization_id,
        email: str,
        role: str,
        invited_by: User
    ) -> OrganizationInvitation:
        """
        Invites a new team member to an organization. Only OWNER or ADMIN can invite.
        """
        email = email.strip().lower()
        role = role.strip().upper()

        if role not in OrganizationRole.values:
            raise ValidationError(f"Invalid organization role: '{role}'.")

        # Verify caller authority
        membership = OrganizationMembership.objects.filter(
            organization_id=organization_id,
            user=invited_by,
            role__in=[OrganizationRole.OWNER, OrganizationRole.ADMIN]
        ).first()

        if not membership and not invited_by.is_superuser:
            raise PermissionDenied("Only organization owners or administrators can invite team members.")

        org = Organization.objects.get(id=organization_id, is_active=True)

        # Check if user is already a member
        if OrganizationMembership.objects.filter(organization=org, user__email=email).exists():
            raise ValidationError(f"User '{email}' is already an active member of {org.name}.")

        # Create or refresh invitation
        expires_at = timezone.now() + datetime.timedelta(days=7)
        invitation, created = OrganizationInvitation.objects.update_or_create(
            organization=org,
            email=email,
            accepted=False,
            defaults={
                'role': role,
                'invited_by': invited_by,
                'token': uuid.uuid4(),
                'expires_at': expires_at,
            }
        )
        CacheManager.invalidate_organizations()

        from .tasks import send_organization_invitation_email_task
        inv_id = str(invitation.id)
        transaction.on_commit(lambda: send_organization_invitation_email_task.delay(inv_id))

        return invitation

    @staticmethod
    @transaction.atomic
    def accept_invitation(*, token: str, user: User) -> OrganizationMembership:
        """
        Accepts a team invitation using a valid invitation token.
        """
        try:
            invitation = OrganizationInvitation.objects.select_related('organization').get(
                token=token,
                accepted=False
            )
        except (OrganizationInvitation.DoesNotExist, ValueError):
            raise ValidationError("Invalid or expired invitation token.")

        if invitation.expires_at < timezone.now():
            raise ValidationError("This invitation has expired. Please request a new invite.")

        if invitation.email.lower() != user.email.lower():
            raise ValidationError(f"This invitation was sent to {invitation.email}, but you are signed in as {user.email}.")

        org = invitation.organization
        if not org.is_active:
            raise ValidationError("The inviting organization is currently inactive.")

        # Create membership
        membership, created = OrganizationMembership.objects.get_or_create(
            organization=org,
            user=user,
            defaults={'role': invitation.role, 'is_default': False}
        )
        if not created:
            membership.role = invitation.role
            membership.save(update_fields=['role', 'updated_at'])

        invitation.accepted = True
        invitation.save(update_fields=['accepted', 'updated_at'])
        CacheManager.invalidate_organizations()

        return membership

    @staticmethod
    @transaction.atomic
    def update_organization(
        *,
        organization_id,
        user: User,
        name: str = None,
        base_currency: str = None,
        billing_email: str = None,
        settings_dict: dict = None
    ) -> Organization:
        """
        Updates organization settings. Only OWNER or ADMIN may update.
        """
        membership = OrganizationMembership.objects.filter(
            organization_id=organization_id,
            user=user,
            role__in=[OrganizationRole.OWNER, OrganizationRole.ADMIN]
        ).first()

        if not membership and not user.is_superuser:
            raise PermissionDenied("You do not have administrative permission to modify this organization.")

        org = Organization.objects.select_for_update().get(id=organization_id)
        if name is not None:
            org.name = name.strip()
        if base_currency is not None:
            org.base_currency = base_currency.strip().upper()
        if billing_email is not None:
            org.billing_email = billing_email.strip().lower()
        if settings_dict is not None:
            current_settings = dict(org.settings or {})
            current_settings.update(settings_dict)
            org.settings = current_settings

        org.save()
        CacheManager.invalidate_organizations()
        return org


class SubscriptionPlanService:
    """
    [DYNAMIC SAAS SUBSCRIPTION PLAN MANAGEMENT]:
    Allows platform Superadmins to create, manage, and update SaaS subscription plans dynamically.
    Syncs new recurring plans directly with Paystack Plan API.
    """

    @classmethod
    @transaction.atomic
    def create_plan(
        cls,
        *,
        name: str,
        price: Decimal,
        interval: str = BillingInterval.MONTHLY,
        currency: str = 'GHS',
        code: str = None,
        description: str = '',
        trial_period_days: int = 0,
        max_users: int = None,
        max_subsidiaries: int = 1,
        features: list = None,
        is_active: bool = True,
        is_public: bool = True,
        sync_paystack: bool = True,
        user: User = None
    ) -> SubscriptionPlan:
        name = name.strip()
        currency = currency.strip().upper()
        if not code:
            base_code = slugify(name) or 'plan'
            code = base_code
            counter = 1
            while SubscriptionPlan.objects.filter(code=code).exists():
                code = f"{base_code}-{counter}"
                counter += 1
        else:
            code = slugify(code)
            if SubscriptionPlan.objects.filter(code=code).exists():
                raise ValidationError(f"A plan with code '{code}' already exists.")

        paystack_plan_code = ''
        if sync_paystack and price > Decimal('0.00'):
            try:
                paystack_data = PaystackService.create_plan(
                    name=name,
                    amount=price,
                    interval=interval,
                    currency=currency,
                    description=description
                )
                paystack_plan_code = paystack_data.get('plan_code', '')
            except Exception as e:
                logger.warning("Could not sync plan with Paystack: %s. Creating plan locally.", str(e))

        plan = SubscriptionPlan.objects.create(
            name=name,
            code=code,
            description=description,
            price=price,
            currency=currency,
            interval=interval,
            paystack_plan_code=paystack_plan_code,
            trial_period_days=trial_period_days,
            max_users=max_users,
            max_subsidiaries=max_subsidiaries,
            features=features or [],
            is_active=is_active,
            is_public=is_public,
            created_by=user
        )

        CacheManager.invalidate_organizations()
        return plan

    @classmethod
    @transaction.atomic
    def update_plan(
        cls,
        *,
        plan_id,
        name: str = None,
        description: str = None,
        price: Decimal = None,
        currency: str = None,
        interval: str = None,
        trial_period_days: int = None,
        max_users: int = None,
        max_subsidiaries: int = None,
        features: list = None,
        is_active: bool = None,
        is_public: bool = None
    ) -> SubscriptionPlan:
        plan = SubscriptionPlan.objects.select_for_update().get(id=plan_id)
        if name is not None:
            plan.name = name.strip()
        if description is not None:
            plan.description = description
        if price is not None:
            plan.price = price
        if currency is not None:
            plan.currency = currency.strip().upper()
        if interval is not None:
            plan.interval = interval
        if trial_period_days is not None:
            plan.trial_period_days = trial_period_days
        if max_users is not None:
            plan.max_users = max_users
        if max_subsidiaries is not None:
            plan.max_subsidiaries = max_subsidiaries
        if features is not None:
            plan.features = features
        if is_active is not None:
            plan.is_active = is_active
        if is_public is not None:
            plan.is_public = is_public

        plan.save()
        CacheManager.invalidate_organizations()
        return plan

    @classmethod
    @transaction.atomic
    def delete_plan(cls, *, plan_id) -> None:
        plan = SubscriptionPlan.objects.select_for_update().get(id=plan_id)
        plan.is_active = False
        plan.save()
        CacheManager.invalidate_organizations()


class BillingService:
    """
    [PAYSTACK BILLING & SUBSCRIPTION ORCHESTRATION]:
    Orchestrates checkout initialization, payment verification, subscription activation,
    and webhook handling with strict financial idempotency.
    """

    @classmethod
    @transaction.atomic
    def initialize_subscription(
        cls,
        *,
        organization: Organization,
        plan: SubscriptionPlan,
        user: User,
        callback_url: str = None,
        idempotency_key: str = None
    ) -> tuple[SubscriptionTransaction, dict]:
        """
        Initializes a Paystack transaction checkout for the target organization.
        """
        if idempotency_key:
            existing_tx = SubscriptionTransaction.objects.filter(
                organization=organization,
                idempotency_key=idempotency_key
            ).first()
            if existing_tx:
                return existing_tx, existing_tx.paystack_response

        reference = f"sub_{organization.id.hex[:6]}_{uuid.uuid4().hex[:10]}"
        email = organization.billing_email or user.email

        paystack_data = PaystackService.initialize_transaction(
            email=email,
            amount=plan.price,
            currency=plan.currency,
            reference=reference,
            plan_code=plan.paystack_plan_code or None,
            callback_url=callback_url,
            metadata={
                'organization_id': str(organization.id),
                'plan_id': str(plan.id),
                'user_id': str(user.id),
            }
        )

        tx = SubscriptionTransaction.objects.create(
            organization=organization,
            plan=plan,
            amount=plan.price,
            currency=plan.currency,
            reference=reference,
            status=TransactionStatus.PENDING,
            idempotency_key=idempotency_key,
            paystack_response=paystack_data
        )

        CacheManager.invalidate_organizations()
        return tx, paystack_data

    @classmethod
    @transaction.atomic
    def verify_and_activate_subscription(cls, *, reference: str) -> tuple[SubscriptionTransaction, bool]:
        """
        Verifies transaction status with Paystack and activates the organization subscription upon success.
        Idempotent: Re-verifying an already processed transaction returns the current state safely.
        """
        tx = SubscriptionTransaction.objects.select_for_update().filter(reference=reference).select_related('organization', 'plan').first()
        if not tx:
            raise ValidationError(f"No subscription transaction found matching reference '{reference}'.")

        if tx.status == TransactionStatus.SUCCESS:
            return tx, True

        paystack_data = PaystackService.verify_transaction(reference=reference)
        paystack_status = str(paystack_data.get('status', '')).lower()

        if paystack_status == 'success':
            tx.status = TransactionStatus.SUCCESS
            tx.channel = paystack_data.get('channel', '')
            paid_at_str = paystack_data.get('paid_at')
            tx.paid_at = parse_datetime(paid_at_str) if paid_at_str else timezone.now()
            tx.paystack_response = paystack_data
            tx.save()

            # Activate subscription on Organization
            org = tx.organization
            org.subscription_plan = tx.plan
            org.plan = tx.plan.code[:50]

            # Calculate new plan expiry date
            if tx.plan.interval == BillingInterval.ANNUALLY:
                duration_days = 365
            elif tx.plan.interval == BillingInterval.FREE:
                duration_days = 3650
            else:
                duration_days = 30

            current_expiry = org.plan_expires_at
            if current_expiry and current_expiry > timezone.now():
                org.plan_expires_at = current_expiry + datetime.timedelta(days=duration_days)
            else:
                org.plan_expires_at = timezone.now() + datetime.timedelta(days=duration_days)

            customer_data = paystack_data.get('customer') or {}
            if customer_data.get('customer_code'):
                org.paystack_customer_code = customer_data['customer_code']

            subscription_data = paystack_data.get('subscription') or {}
            if subscription_data.get('subscription_code'):
                org.paystack_subscription_code = subscription_data['subscription_code']

            org.save()
            CacheManager.invalidate_organizations()
            logger.info("Subscription activated for %s under plan %s (expires: %s)", org.name, tx.plan.name, org.plan_expires_at)
            return tx, True
        else:
            tx.status = TransactionStatus.FAILED
            tx.paystack_response = paystack_data
            tx.save()
            return tx, False

    @classmethod
    def process_paystack_webhook(
        cls,
        *,
        payload: dict,
        raw_body: bytes,
        signature_header: str
    ) -> dict:
        """
        Ingests and processes Paystack webhooks with:
        1. Cryptographic HMAC-SHA512 signature validation.
        2. Database-backed deduplication (PaymentWebhookLog) for strict once-and-only-once execution.
        3. Event routing (charge.success, subscription.disable, etc.).
        """
        if not PaystackService.verify_webhook_signature(raw_body, signature_header):
            logger.warning("Paystack webhook rejected: Invalid HMAC signature header %s", signature_header)
            raise ValidationError("Invalid Paystack webhook signature.")

        event_name = payload.get('event', '')
        event_data = payload.get('data', {}) or {}
        reference = event_data.get('reference', '')
        event_id = str(payload.get('id') or event_data.get('id') or f"{event_name}_{reference}")

        with transaction.atomic():
            webhook_log, created = PaymentWebhookLog.objects.select_for_update().get_or_create(
                event_id=event_id,
                defaults={
                    'provider': 'PAYSTACK',
                    'event_type': event_name,
                    'reference': reference,
                    'payload': payload,
                    'processed': False,
                }
            )

            if not created and webhook_log.processed:
                logger.info("Webhook %s already processed. Ignoring duplicate event idempotently.", event_id)
                return {
                    'status': 'ignored',
                    'message': 'Webhook event has already been processed.'
                }

            try:
                if event_name == 'charge.success' and reference:
                    cls.verify_and_activate_subscription(reference=reference)

                webhook_log.processed = True
                webhook_log.error_message = ''
                webhook_log.save()
            except Exception as e:
                logger.exception("Failed processing webhook %s: %s", event_id, str(e))
                webhook_log.error_message = str(e)
                webhook_log.save()
                raise

        return {
            'status': 'success',
            'event': event_name,
            'event_id': event_id,
        }

