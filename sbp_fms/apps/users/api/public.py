from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema
from apps.common.responses import api_success
from apps.users.services import UserService
from apps.users.serializers import (
    UserLoginInputSerializer, UserOutputSerializer,
    UserAuthTokensSerializer, UserMeOutputSerializer
)


class UserLoginPublicApi(APIView):
    """
    [PUBLIC API]:
    Authenticates user and returns JWT token pair (access & refresh) alongside user role and permissions.
    """
    permission_classes = [AllowAny]

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


