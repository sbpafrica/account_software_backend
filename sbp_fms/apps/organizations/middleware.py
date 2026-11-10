from typing import Optional
from django.utils.deprecation import MiddlewareMixin
from .models import Organization, OrganizationMembership
from .context import set_current_organization, clear_current_organization


class TenantMiddleware(MiddlewareMixin):
    """
    [SAAS MULTI-TENANT MIDDLEWARE]:
    Resolves and binds the active tenant Organization to:
    1. `request.organization`
    2. Thread-local ContextVar via `set_current_organization(org)`

    Resolution priority:
    1. HTTP Header: 'X-Organization-ID' (UUID or slug)
    2. Subdomain: e.g. <subdomain>.domain.com
    3. User's active JWT claim / Default OrganizationMembership
    """

    def process_request(self, request):
        clear_current_organization()
        request.organization = None

        org = self._resolve_organization(request)
        if org:
            request.organization = org
            set_current_organization(org)

    def process_response(self, request, response):
        clear_current_organization()
        if hasattr(request, 'organization') and request.organization:
            response['X-Organization-ID'] = str(request.organization.id)
            response['X-Organization-Slug'] = request.organization.slug
        return response

    def _resolve_organization(self, request) -> Optional[Organization]:
        # 1. Check HTTP Header: X-Organization-ID (UUID or slug)
        org_identifier = request.headers.get('X-Organization-ID') or request.META.get('HTTP_X_ORGANIZATION_ID')
        if org_identifier:
            try:
                import uuid
                try:
                    uuid_obj = uuid.UUID(org_identifier)
                    org = Organization.objects.filter(id=uuid_obj, is_active=True).first()
                except ValueError:
                    org = Organization.objects.filter(slug=org_identifier, is_active=True).first()
                if org:
                    return org
            except Exception:
                pass

        # 2. Check Subdomain (e.g. acme.sbpfms.com)
        try:
            host = request.get_host().split(':')[0]
            host_parts = host.split('.')
            if len(host_parts) >= 3 and host_parts[0] not in ('api', 'www', 'localhost', '127'):
                subdomain = host_parts[0].lower()
                org = Organization.objects.filter(subdomain=subdomain, is_active=True).first()
                if org:
                    return org
        except Exception:
            pass

        # 3. Check JWT claims in Authorization Header
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
        if auth_header and (auth_header.startswith('Bearer ') or auth_header.startswith('JWT ')):
            try:
                token_str = auth_header.split(' ', 1)[1]
                from rest_framework_simplejwt.tokens import AccessToken
                token = AccessToken(token_str)
                org_id = token.get('org_id')
                if org_id:
                    org = Organization.objects.filter(id=org_id, is_active=True).first()
                    if org:
                        return org
            except Exception:
                pass

        # 4. Check Authenticated User Default Membership (Session or DRF authenticated)
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            membership = OrganizationMembership.objects.filter(
                user=user,
                organization__is_active=True
            ).select_related('organization').order_by('-is_default', 'created_at').first()
            if membership:
                return membership.organization

        return None
