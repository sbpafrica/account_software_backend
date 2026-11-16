import logging
from rest_framework.throttling import SimpleRateThrottle, AnonRateThrottle, UserRateThrottle
from apps.organizations.context import get_current_organization

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """
    Extracts the true client IP address, properly handling reverse proxies
    (Nginx / Cloudflare / AWS ELB) via X-Forwarded-For or X-Real-IP headers.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # First IP in X-Forwarded-For chain is the originating client IP
        return xff.split(',')[0].strip()
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


class SuperuserBypassMixin:
    """
    Allows Platform Superusers to bypass rate limits for administrative tasks.
    """
    def allow_request(self, request, view):
        if request.user and request.user.is_authenticated and getattr(request.user, 'is_superuser', False):
            return True
        return super().allow_request(request, view)


class SbpAnonRateThrottle(AnonRateThrottle):
    """
    [RATE LIMITER - ANONYMOUS CLIENTS]:
    Protects public endpoints (e.g. docs, schema, health check) against automated scraping and volumetric abuse.
    Keyed on client IP address.
    """
    scope = 'anon'

    def get_ident(self, request):
        return get_client_ip(request)


class SbpUserRateThrottle(SuperuserBypassMixin, UserRateThrottle):
    """
    [RATE LIMITER - AUTHENTICATED USERS]:
    Standard per-user API rate limit across all standard authenticated endpoints.
    Keyed on user ID.
    """
    scope = 'user'


class AuthBurstRateThrottle(SimpleRateThrottle):
    """
    [RATE LIMITER - AUTHENTICATION BURST]:
    Strict brute-force prevention on credential verification endpoints (login, password reset).
    Limits rapid burst login attempts per IP + targeted account.
    """
    scope = 'auth_burst'

    def get_cache_key(self, request, view):
        ident = get_client_ip(request)
        username = ''
        if hasattr(request, 'data') and isinstance(request.data, dict):
            username = str(request.data.get('email') or request.data.get('username') or '').strip().lower()

        key_ident = f"{ident}_{username}" if username else ident
        return self.cache_format % {
            'scope': self.scope,
            'ident': key_ident
        }


class AuthSustainedRateThrottle(SimpleRateThrottle):
    """
    [RATE LIMITER - AUTHENTICATION SUSTAINED]:
    Prevents low-and-slow credential stuffing attacks against authentication endpoints over extended time windows.
    """
    scope = 'auth_sustained'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request)
        }


class RegistrationRateThrottle(SimpleRateThrottle):
    """
    [RATE LIMITER - SAAS TENANT ONBOARDING]:
    Restricts automated bot registration of new organization tenants.
    Keyed on client IP address.
    """
    scope = 'registration'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request)
        }


class FinancialMutationRateThrottle(SuperuserBypassMixin, SimpleRateThrottle):
    """
    [RATE LIMITER - FINANCIAL TRANSACTION MUTATIONS]:
    Throttles high-consequence state mutations (journal entry postings, payment vouchers,
    bank reconciliation runs, and billing checkout initialization) to prevent double execution
    and rapid financial replay attacks.
    """
    scope = 'financial_mutation'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            org = get_current_organization()
            org_id = str(org.id) if org else 'no_org'
            return self.cache_format % {
                'scope': self.scope,
                'ident': f"org_{org_id}_user_{request.user.id}"
            }
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request)
        }


class TenantRateThrottle(SuperuserBypassMixin, SimpleRateThrottle):
    """
    [RATE LIMITER - MULTI-TENANT FAIR SHARE]:
    Ensures no single organization tenant can starve database capacity or exhaust connection pools
    for other tenants on the shared infrastructure.
    Keyed strictly on Organization ID.
    """
    scope = 'tenant'

    def get_cache_key(self, request, view):
        org = get_current_organization()
        if org:
            return self.cache_format % {
                'scope': self.scope,
                'ident': f"tenant_{org.id}"
            }
        return None  # Fall through if no organization context
