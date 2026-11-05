from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from apps.users.services import UserService
from apps.users.serializers import UserLoginInputSerializer, UserOutputSerializer


class UserLoginPublicApi(APIView):
    """
    [PUBLIC API]:
    Authenticates user and returns JWT token pair (access & refresh) alongside user role and permissions.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, tokens = UserService.user_authenticate(**serializer.validated_data)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'token': tokens['access'],  # For backward-compatibility with Bearer token clients
            'user': UserOutputSerializer(user).data,
            'permissions': user.get_all_permissions()
        }, status=status.HTTP_200_OK)


class UserMePublicApi(APIView):
    """
    [AUTHENTICATED API]:
    Returns current authenticated user profile, assigned role, country scope, and active permissions list.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'user': UserOutputSerializer(user).data,
            'permissions': user.get_all_permissions()
        })
