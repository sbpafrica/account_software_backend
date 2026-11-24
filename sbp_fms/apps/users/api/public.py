from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import exceptions, status
from drf_spectacular.utils import extend_schema
from apps.common.responses import api_success
from apps.common.throttling import AuthBurstRateThrottle, AuthSustainedRateThrottle
from apps.users.services import UserService
from apps.users.serializers import (
    UserLoginInputSerializer, UserOutputSerializer,
    UserAuthTokensSerializer, UserMeOutputSerializer,
    UserPasswordChangeInputSerializer, UserForgotPasswordInputSerializer,
    UserPasswordResetConfirmInputSerializer
)


class UserLoginPublicApi(APIView):
    """
    [PUBLIC API]:
    Authenticates user and returns JWT token pair (access & refresh) alongside user role and permissions.
    Protected against brute-force and credential stuffing by burst and sustained rate throttles.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstRateThrottle, AuthSustainedRateThrottle]

    @extend_schema(
        tags=['Users - Authentication'],
        operation_id='public_user_login',
        summary='Authenticate user and generate JWT tokens',
        description='Takes user email and password, returning JWT access & refresh tokens with assigned role and permissions.',
        request=UserLoginInputSerializer,
        responses={
            status.HTTP_200_OK: UserAuthTokensSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
        }
    )
    def post(self, request):
        serializer = UserLoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = UserService.user_authenticate(**serializer.validated_data)

        payload = {
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'token': tokens['access'],  # For backward-compatibility with Bearer token clients
            'user': UserOutputSerializer(user).data,
            'permissions': user.get_all_permissions()
        }
        return api_success(data=payload, message="Authentication successful.", status_code=status.HTTP_200_OK)


class UserMePublicApi(APIView):
    """
    [AUTHENTICATED API]:
    Returns current authenticated user profile, assigned role, country scope, and active permissions list.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Users - Authentication'],
        operation_id='public_user_me',
        summary='Retrieve authenticated user profile',
        description='Returns current authenticated user profile, primary role, country scope, and active permissions.',
        responses={
            status.HTTP_200_OK: UserMeOutputSerializer,
            status.HTTP_401_UNAUTHORIZED: dict,
        }
    )
    def get(self, request):
        user = request.user
        payload = {
            'user': UserOutputSerializer(user).data,
            'permissions': user.get_all_permissions()
        }
        return api_success(data=payload, message="User profile retrieved successfully.")


class UserPasswordChangePublicApi(APIView):
    """
    [AUTHENTICATED API]:
    Allows logged-in users to securely change their password.
    Requires current password and new password (min 8 chars).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Users - Authentication'],
        operation_id='public_user_password_change',
        summary='Change password for current authenticated user',
        description='Validates the current password and sets a new password for the logged-in user.',
        request=UserPasswordChangeInputSerializer,
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
        }
    )
    def post(self, request):
        serializer = UserPasswordChangeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            UserService.password_change(
                user=request.user,
                current_password=serializer.validated_data['current_password'],
                new_password=serializer.validated_data['new_password']
            )
            return api_success(message="Password successfully changed.")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class UserForgotPasswordPublicApi(APIView):
    """
    [PUBLIC API]:
    Initiates password reset workflow.
    Generates a secure, 24-hour token and emails a password reset link.
    Protected against brute-force and credential stuffing by rate limits.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstRateThrottle, AuthSustainedRateThrottle]

    @extend_schema(
        tags=['Users - Authentication'],
        operation_id='public_user_password_forgot',
        summary='Request password reset link via email',
        description='Sends a secure password reset link containing a one-time token to the user email address.',
        request=UserForgotPasswordInputSerializer,
        responses={
            status.HTTP_200_OK: dict,
        }
    )
    def post(self, request):
        serializer = UserForgotPasswordInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        UserService.password_forgot_request(
            email=serializer.validated_data['email'],
            frontend_url=serializer.validated_data.get('frontend_url')
        )
        return api_success(
            message="If an account exists with this email, a password reset link has been dispatched."
        )


class UserPasswordResetConfirmPublicApi(APIView):
    """
    [PUBLIC API]:
    Confirms password reset using one-time token and base64 user ID from email.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstRateThrottle, AuthSustainedRateThrottle]

    @extend_schema(
        tags=['Users - Authentication'],
        operation_id='public_user_password_reset_confirm',
        summary='Confirm password reset using token and set new password',
        description='Validates the password reset token and updates the user account with the new password.',
        request=UserPasswordResetConfirmInputSerializer,
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
        }
    )
    def post(self, request):
        serializer = UserPasswordResetConfirmInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            UserService.password_reset_confirm(
                uidb64=serializer.validated_data['uid'],
                token=serializer.validated_data['token'],
                new_password=serializer.validated_data['new_password']
            )
            return api_success(message="Password has been successfully reset. You can now log in.")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})



