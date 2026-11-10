from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class SBPTokenAuthentication(JWTAuthentication):
    """
    [JWT AUTHENTICATION]:
    SBP Africa enterprise authentication using Django REST Framework JWT (rest_framework_simplejwt).
    Accepts standard 'Authorization: Bearer <access_token>' or 'Authorization: JWT <access_token>'.
    """
    pass


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class SBPTokenAuthenticationScheme(OpenApiAuthenticationExtension):
        target_class = 'apps.users.authentication.SBPTokenAuthentication'
        name = 'sbpTokenAuth'

        def get_security_definition(self, auto_schema):
            return {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
except ImportError:
    pass



class JWTTokenService:
    """
    Service for generating and managing JWT token pairs for users.
    Enriches JWT claims with role, country scope, superuser status, and active SaaS tenant organization.
    """
    @staticmethod
    def get_tokens_for_user(user: User, organization=None) -> dict:
        refresh = RefreshToken.for_user(user)

        # Custom claims embedded in the JWT payload
        refresh['email'] = user.email
        refresh['role'] = user.role.name if user.role else None
        refresh['assigned_country'] = user.assigned_country
        refresh['is_superuser'] = user.is_superuser

        # Multi-tenant SaaS organization claims
        org_role = None
        if organization is None:
            # Check user's default organization membership
            try:
                membership = user.organization_memberships.select_related('organization').filter(
                    organization__is_active=True
                ).order_by('-is_default', 'created_at').first()
                if membership:
                    organization = membership.organization
                    org_role = membership.role
            except Exception:
                pass
        else:
            try:
                membership = user.organization_memberships.filter(organization=organization).first()
                if membership:
                    org_role = membership.role
            except Exception:
                pass

        if organization:
            refresh['org_id'] = str(organization.id)
            refresh['org_slug'] = organization.slug
            refresh['org_name'] = organization.name
            refresh['org_role'] = org_role
        else:
            refresh['org_id'] = None
            refresh['org_slug'] = None
            refresh['org_name'] = None
            refresh['org_role'] = None

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
