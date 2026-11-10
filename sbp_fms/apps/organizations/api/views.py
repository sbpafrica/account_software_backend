from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.common.responses import api_success, api_error
from apps.common.idempotency import idempotent_endpoint
from apps.users.serializers import UserOutputSerializer
from apps.users.permissions import IsSuperUser
from apps.organizations.models import (
    Organization, OrganizationMembership, OrganizationRole,
    SubscriptionPlan, SubscriptionTransaction, TransactionStatus
)
from apps.organizations.context import get_current_organization
from apps.organizations.services import OrganizationService, SubscriptionPlanService, BillingService
from apps.organizations.selectors import (
    subscription_plans_list, subscription_plan_detail, subscription_transactions_list
)
from apps.organizations.serializers import (
    OrganizationOutputSerializer,
    OrganizationMembershipOutputSerializer,
    OrganizationRegisterInputSerializer,
    OrganizationRegisterOutputSerializer,
    OrganizationSwitchInputSerializer,
    OrganizationSwitchOutputSerializer,
    OrganizationInviteInputSerializer,
    OrganizationInvitationOutputSerializer,
    OrganizationAcceptInviteInputSerializer,
    OrganizationUpdateInputSerializer,
    SubscriptionPlanOutputSerializer,
    SubscriptionPlanInputSerializer,
    BillingInitializeInputSerializer,
    BillingInitializeOutputSerializer,
    BillingVerifyInputSerializer,
    BillingVerifyOutputSerializer,
    SubscriptionTransactionOutputSerializer,
    PaystackWebhookInputSerializer,
)


class OrganizationRegisterPublicApi(APIView):
    """
    [PUBLIC API]:
    Self-service registration endpoint for new B2B SaaS customer organizations.
    Creates the organization tenant, owner account, default company profile, and returns scoped JWT tokens.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='public_organization_register',
        summary='Self-service SaaS customer registration',
        description=(
            'Onboards a new customer organization onto the platform. '
            'Provisions a trial organization, owner user, initial ledger profile, '
            'and returns JWT access and refresh tokens bound to the new tenant.'
        ),
        request=OrganizationRegisterInputSerializer,
        responses={
            status.HTTP_201_CREATED: OrganizationRegisterOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Validation error during registration"),
        }
    )
    def post(self, request):
        serializer = OrganizationRegisterInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            org, user, tokens = OrganizationService.register_customer(**serializer.validated_data)
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        payload = {
            'organization': OrganizationOutputSerializer(org).data,
            'user': UserOutputSerializer(user).data,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
        }
        return api_success(
            data=payload,
            message=f"Organization '{org.name}' successfully registered.",
            status_code=status.HTTP_201_CREATED
        )


class OrganizationMeListApi(APIView):
    """
    [AUTHENTICATED API]:
    Lists all organization tenants that the authenticated user belongs to.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='user_organizations_me_list',
        summary="List user's organization memberships",
        description="Returns all active organizations the authenticated user belongs to along with their assigned role and default tenant status.",
        responses={
            status.HTTP_200_OK: OrganizationMembershipOutputSerializer(many=True),
        }
    )
    def get(self, request):
        memberships = OrganizationService.list_user_organizations(user=request.user)
        data = OrganizationMembershipOutputSerializer(memberships, many=True).data
        return api_success(data=data, message="User organizations retrieved successfully.")


class OrganizationSwitchApi(APIView):
    """
    [AUTHENTICATED API]:
    Switches the user's active tenant organization and returns new JWT access and refresh tokens.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='user_organization_switch',
        summary='Switch active tenant organization',
        description='Generates a new JWT token pair scoped to the requested organization for multi-tenant users or outsourced accountants.',
        request=OrganizationSwitchInputSerializer,
        responses={
            status.HTTP_200_OK: OrganizationSwitchOutputSerializer,
            status.HTTP_403_FORBIDDEN: OpenApiResponse(description="User does not have access to this organization"),
        }
    )
    def post(self, request):
        serializer = OrganizationSwitchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = OrganizationService.switch_organization(
                user=request.user,
                organization_id=serializer.validated_data['organization_id']
            )
        except PermissionDenied as e:
            return api_error(message=str(e), status_code=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        payload = {
            'access': result['tokens']['access'],
            'refresh': result['tokens']['refresh'],
            'organization': OrganizationOutputSerializer(result['organization']).data,
            'role': result['role'],
        }
        return api_success(data=payload, message=f"Switched to organization '{result['organization'].name}'.")


class OrganizationInviteApi(APIView):
    """
    [AUTHENTICATED API]:
    Invites a colleague or team member to join the tenant organization.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='organization_invite_member',
        summary='Invite team member to organization',
        description='Generates an invitation token for a new user to join the tenant with a designated role (Admin, Accountant, Clerk, etc.).',
        request=OrganizationInviteInputSerializer,
        responses={
            status.HTTP_201_CREATED: OrganizationInvitationOutputSerializer,
            status.HTTP_403_FORBIDDEN: OpenApiResponse(description="Caller lacks admin or owner permission"),
        }
    )
    def post(self, request):
        serializer = OrganizationInviteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = OrganizationService.invite_member(
                invited_by=request.user,
                **serializer.validated_data
            )
        except PermissionDenied as e:
            return api_error(message=str(e), status_code=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        data = OrganizationInvitationOutputSerializer(invitation).data
        return api_success(data=data, message="Invitation created successfully.", status_code=status.HTTP_201_CREATED)


class OrganizationAcceptInviteApi(APIView):
    """
    [AUTHENTICATED API]:
    Accepts an invitation using an invitation token.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='organization_accept_invite',
        summary='Accept team invitation',
        description='Binds the authenticated user into the inviting organization according to the token payload.',
        request=OrganizationAcceptInviteInputSerializer,
        responses={
            status.HTTP_200_OK: OrganizationMembershipOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Expired or invalid invitation"),
        }
    )
    def post(self, request):
        serializer = OrganizationAcceptInviteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = OrganizationService.accept_invitation(
                token=str(serializer.validated_data['token']),
                user=request.user
            )
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        data = OrganizationMembershipOutputSerializer(membership).data
        return api_success(data=data, message=f"Successfully joined {membership.organization.name}.")


class OrganizationDetailApi(APIView):
    """
    [AUTHENTICATED API]:
    Retrieves or updates details and settings of a specific organization.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='organization_detail_get',
        summary='Retrieve organization details',
        description='Fetches organization metadata, subscription plan, base currency, and branding settings.',
        responses={
            status.HTTP_200_OK: OrganizationOutputSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Organization not found"),
        }
    )
    def get(self, request, organization_id):
        org = get_object_or_404(Organization, id=organization_id, is_active=True)
        # Verify caller has membership or is superuser
        if not OrganizationMembership.objects.filter(organization=org, user=request.user).exists() and not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this organization.")
        data = OrganizationOutputSerializer(org).data
        return api_success(data=data)

    @extend_schema(
        tags=['Organizations & Multi-Tenancy'],
        operation_id='organization_detail_update',
        summary='Update organization settings',
        description='Updates organization legal name, reporting currency, billing email, or JSON settings dictionary.',
        request=OrganizationUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: OrganizationOutputSerializer,
            status.HTTP_403_FORBIDDEN: OpenApiResponse(description="Insufficient permissions"),
        }
    )
    def patch(self, request, organization_id):
        serializer = OrganizationUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            org = OrganizationService.update_organization(
                organization_id=organization_id,
                user=request.user,
                name=serializer.validated_data.get('name'),
                base_currency=serializer.validated_data.get('base_currency'),
                billing_email=serializer.validated_data.get('billing_email'),
                settings_dict=serializer.validated_data.get('settings'),
            )
        except PermissionDenied as e:
            return api_error(message=str(e), status_code=status.HTTP_403_FORBIDDEN)

        data = OrganizationOutputSerializer(org).data
        return api_success(data=data, message="Organization settings updated successfully.")


# ============================================================================
# SUBSCRIPTION PLANS & PAYSTACK BILLING APIS
# ============================================================================

class SubscriptionPlanListPublicApi(APIView):
    """
    [PUBLIC API]:
    Lists all available SaaS subscription plans and tiers for display on pricing page and customer selection.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='billing_public_plans_list',
        summary='List public SaaS subscription plans',
        description='Retrieves all active, publicly available subscription plans including pricing, interval, feature matrix, and limits.',
        responses={
            status.HTTP_200_OK: SubscriptionPlanOutputSerializer(many=True),
        }
    )
    def get(self, request):
        plans = subscription_plans_list(public_only=True)
        data = SubscriptionPlanOutputSerializer(plans, many=True).data
        return api_success(data=data, message="Public subscription plans retrieved successfully.")


class SubscriptionPlanListCreateAdminApi(APIView):
    """
    [SUPERADMIN API]:
    Allows Superadmins to retrieve all plans (including internal) and create new dynamic subscription plans.
    Integrates dynamically with Paystack Plan API when sync_paystack=True.
    Supports strict financial idempotency via 'Idempotency-Key' header.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='admin_billing_plans_list',
        summary='[Admin] List all subscription plans',
        description='Superadmin endpoint to list all subscription plans including active, inactive, and internal tiers.',
        responses={
            status.HTTP_200_OK: SubscriptionPlanOutputSerializer(many=True),
        }
    )
    def get(self, request):
        plans = subscription_plans_list(public_only=False)
        data = SubscriptionPlanOutputSerializer(plans, many=True).data
        return api_success(data=data, message="All subscription plans retrieved successfully.")

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='admin_billing_plan_create',
        summary='[Admin] Create dynamic subscription plan',
        description=(
            'Allows Superadmin to define a new SaaS subscription plan dynamically with custom pricing, '
            'feature sets, user limits, and intervals. Automatically syncs with Paystack Plan API.'
        ),
        request=SubscriptionPlanInputSerializer,
        responses={
            status.HTTP_201_CREATED: SubscriptionPlanOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Validation error in plan configuration"),
            status.HTTP_409_CONFLICT: OpenApiResponse(description="Concurrent operation in progress for idempotency key"),
        }
    )
    @idempotent_endpoint()
    def post(self, request):
        serializer = SubscriptionPlanInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = SubscriptionPlanService.create_plan(
                user=request.user,
                **serializer.validated_data
            )
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        data = SubscriptionPlanOutputSerializer(plan).data
        return api_success(
            data=data,
            message=f"Subscription plan '{plan.name}' created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class SubscriptionPlanDetailAdminApi(APIView):
    """
    [SUPERADMIN API]:
    Retrieve, update, or soft-delete a specific subscription plan.
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='admin_billing_plan_detail',
        summary='[Admin] Retrieve plan details',
        description='Fetches full details of a specific subscription plan by UUID.',
        responses={
            status.HTTP_200_OK: SubscriptionPlanOutputSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Plan not found"),
        }
    )
    def get(self, request, plan_id):
        plan = subscription_plan_detail(plan_id=plan_id)
        data = SubscriptionPlanOutputSerializer(plan).data
        return api_success(data=data)

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='admin_billing_plan_update',
        summary='[Admin] Update subscription plan',
        description='Updates configuration, pricing, or status of an existing subscription plan.',
        request=SubscriptionPlanInputSerializer,
        responses={
            status.HTTP_200_OK: SubscriptionPlanOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Validation error"),
        }
    )
    def patch(self, request, plan_id):
        serializer = SubscriptionPlanInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop('sync_paystack', None)
        try:
            plan = SubscriptionPlanService.update_plan(plan_id=plan_id, **data)
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        out = SubscriptionPlanOutputSerializer(plan).data
        return api_success(data=out, message=f"Subscription plan '{plan.name}' updated successfully.")

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='admin_billing_plan_delete',
        summary='[Admin] Soft-delete subscription plan',
        description='Deactivates a subscription plan so it is no longer available for new subscriptions.',
        responses={
            status.HTTP_200_OK: OpenApiResponse(description="Plan deactivated successfully"),
        }
    )
    def delete(self, request, plan_id):
        SubscriptionPlanService.delete_plan(plan_id=plan_id)
        return api_success(message="Subscription plan successfully deactivated.")


class BillingInitializeApi(APIView):
    """
    [AUTHENTICATED TENANT API]:
    Initializes a Paystack subscription checkout for the active organization.
    Secured with strict financial idempotency ('Idempotency-Key' header).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='billing_initialize_checkout',
        summary='Initialize Paystack subscription checkout',
        description=(
            'Initiates an online checkout session with Paystack for the active tenant organization. '
            'Returns the secure Paystack authorization checkout URL and reference. '
            'Supports Idempotency-Key header to prevent duplicate charge attempts.'
        ),
        request=BillingInitializeInputSerializer,
        responses={
            status.HTTP_201_CREATED: BillingInitializeOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Invalid plan or checkout parameters"),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(description="Caller lacks billing authority for organization"),
            status.HTTP_409_CONFLICT: OpenApiResponse(description="Concurrent charge operation in progress"),
        }
    )
    @idempotent_endpoint()
    def post(self, request):
        serializer = BillingInitializeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_id = serializer.validated_data['plan_id']
        callback_url = serializer.validated_data.get('callback_url')

        # Resolve organization
        org = get_current_organization()
        if not org:
            membership = OrganizationMembership.objects.filter(user=request.user, is_default=True).first()
            if membership:
                org = membership.organization

        if not org:
            return api_error(message="No active organization found for billing checkout.", status_code=status.HTTP_400_BAD_REQUEST)

        # Check billing permission (OWNER, ADMIN, or platform superuser)
        has_perm = request.user.is_superuser or OrganizationMembership.objects.filter(
            organization=org,
            user=request.user,
            role__in=[OrganizationRole.OWNER, OrganizationRole.ADMIN]
        ).exists()
        if not has_perm:
            raise PermissionDenied("Only organization owners or administrators can initialize billing subscriptions.")

        plan = subscription_plan_detail(plan_id=plan_id)
        idempotency_key = (
            request.headers.get('Idempotency-Key')
            or request.headers.get('X-Idempotency-Key')
        )

        try:
            tx, init_data = BillingService.initialize_subscription(
                organization=org,
                plan=plan,
                user=request.user,
                callback_url=callback_url,
                idempotency_key=idempotency_key
            )
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        payload = {
            'authorization_url': init_data.get('authorization_url', ''),
            'access_code': init_data.get('access_code', ''),
            'reference': tx.reference,
            'amount': plan.price,
            'currency': plan.currency,
        }
        return api_success(
            data=payload,
            message="Checkout initialized successfully. Redirect user to authorization_url.",
            status_code=status.HTTP_201_CREATED
        )


class BillingVerifyApi(APIView):
    """
    [AUTHENTICATED TENANT API]:
    Synchronously verifies Paystack payment completion and activates the organization subscription.
    Idempotent: Safe for repetitive verification calls.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='billing_verify_transaction',
        summary='Verify Paystack payment and activate subscription',
        description=(
            'Queries Paystack API to verify transaction status. If successful, activates the subscription, '
            'extends the tenant validity period, and updates customer tokens. Safe for repeated calls.'
        ),
        request=BillingVerifyInputSerializer,
        responses={
            status.HTTP_200_OK: BillingVerifyOutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Verification failed or reference not found"),
            status.HTTP_409_CONFLICT: OpenApiResponse(description="Concurrent operation in progress"),
        }
    )
    @idempotent_endpoint()
    def post(self, request):
        serializer = BillingVerifyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reference = serializer.validated_data['reference']

        try:
            tx, success = BillingService.verify_and_activate_subscription(reference=reference)
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        tx_data = SubscriptionTransactionOutputSerializer(tx).data if tx else None
        org_data = OrganizationOutputSerializer(tx.organization).data if tx else None

        msg = "Payment verified and subscription activated successfully." if success else "Transaction payment verification failed."
        payload = {
            'status': tx.status if tx else TransactionStatus.FAILED,
            'message': msg,
            'transaction': tx_data,
            'organization': org_data,
        }
        return api_success(data=payload, message=msg)


class BillingTransactionsListApi(APIView):
    """
    [AUTHENTICATED TENANT API]:
    Lists all subscription checkout and renewal transactions for the active organization.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='billing_transactions_list',
        summary='List organization billing transactions',
        description='Returns transaction audit history, receipts, amounts, and statuses for the tenant organization.',
        responses={
            status.HTTP_200_OK: SubscriptionTransactionOutputSerializer(many=True),
        }
    )
    def get(self, request):
        org = get_current_organization()
        if not org:
            membership = OrganizationMembership.objects.filter(user=request.user, is_default=True).first()
            if membership:
                org = membership.organization

        if not org:
            return api_error(message="No active organization found.", status_code=status.HTTP_400_BAD_REQUEST)

        txs = subscription_transactions_list(organization_id=org.id)
        data = SubscriptionTransactionOutputSerializer(txs, many=True).data
        return api_success(data=data, message="Billing transactions retrieved successfully.")


class PaystackWebhookPublicApi(APIView):
    """
    [PUBLIC WEBHOOK API]:
    Ingests asynchronous event webhooks from Paystack.
    Enforces HMAC-SHA512 cryptographic verification and strict once-only idempotency via PaymentWebhookLog.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Subscription Plans & Billing'],
        operation_id='billing_paystack_webhook',
        summary='Paystack payment webhook receiver',
        description=(
            'Receives Paystack webhooks (e.g. charge.success, invoice.payment_failed). '
            'Cryptographically verifies X-Paystack-Signature against PAYSTACK_SECRET_KEY, '
            'records PaymentWebhookLog to prevent replay attacks, and activates customer plans.'
        ),
        request=PaystackWebhookInputSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(description="Webhook processed or safely acknowledged"),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Invalid signature or malformed payload"),
        }
    )
    def post(self, request):
        signature = (
            request.headers.get('x-paystack-signature')
            or request.headers.get('X-Paystack-Signature')
            or request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        )
        raw_body = request.body

        try:
            result = BillingService.process_paystack_webhook(
                payload=request.data,
                raw_body=raw_body,
                signature_header=signature
            )
        except ValidationError as e:
            return api_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return api_error(message=f"Webhook processing error: {str(e)}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return api_success(data=result, message="Webhook received and processed successfully.")

