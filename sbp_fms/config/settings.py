import os
import sys
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

# Automatically load environment variables from .env if present (root or app dir)
for _env_candidate in [ROOT_DIR / '.env', BASE_DIR / '.env']:
    if _env_candidate.is_file():
        try:
            with open(_env_candidate, 'r', encoding='utf-8') as _ef:
                for _line in _ef:
                    _line = _line.strip()
                    if not _line or _line.startswith('#') or '=' not in _line:
                        continue
                    _k, _v = _line.split('=', 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
        except Exception:
            pass
        break

DEBUG = os.environ.get('DEBUG', '1').strip().lower() in ('1', 'true', 'yes', 'on')
IS_TESTING = 'pytest' in sys.modules or 'test' in sys.argv or os.environ.get('TESTING') == '1'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-key-sbp-africa-2026'
    else:
        raise ValueError("The SECRET_KEY environment variable must be set in production when DEBUG=False.")

allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '*' if DEBUG else '')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()] if allowed_hosts_env else []

# Custom User Model
AUTH_USER_MODEL = 'users.User'

INSTALLED_APPS = [
    # Jazzmin Admin Theme (must precede django.contrib.admin)
    'jazzmin',

    # Built-in essentials
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Common, Users & Multi-Tenant Organizations
    'apps.common.apps.CommonConfig',
    'apps.users.apps.UsersConfig',
    'apps.organizations.apps.OrganizationsConfig',

    # SBP-FMS Domain Apps
    'apps.ledger.apps.LedgerConfig',
    'apps.receivables.apps.ReceivablesConfig',
    'apps.payables.apps.PayablesConfig',
    'apps.payroll_escrow.apps.PayrollEscrowConfig',
    'apps.treasury.apps.TreasuryConfig',
    'apps.taxation.apps.TaxationConfig',
    'apps.assets.apps.AssetsConfig',
    'apps.consolidation.apps.ConsolidationConfig',
    'apps.budgeting.apps.BudgetingConfig',
    'apps.contracts.apps.ContractsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.organizations.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if 'DATABASE_URL' in os.environ and os.environ['DATABASE_URL'].strip():
    db_url_str = os.environ['DATABASE_URL'].strip()
    if db_url_str.startswith('sqlite:'):
        # Handle SQLite URL format: sqlite:///path/to/db.sqlite3 or sqlite://:memory:
        import re
        sqlite_path = re.sub(r'^sqlite:(///?)?', '', db_url_str)
        if not sqlite_path or sqlite_path == ':memory:':
            DATABASES['default'] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        else:
            DATABASES['default'] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / sqlite_path if not os.path.isabs(sqlite_path) else sqlite_path,
            }
    else:
        import urllib.parse
        url = urllib.parse.urlparse(db_url_str)
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': urllib.parse.unquote(url.path[1:]),
            'USER': urllib.parse.unquote(url.username or ''),
            'PASSWORD': urllib.parse.unquote(url.password or ''),
            'HOST': url.hostname or '',
            'PORT': url.port or 5432,
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '600')),
        }

# Multi-Tier Caching: Redis default, LocMem fallback
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sbp_fms_cache',
        'TIMEOUT': 3600,
    }
}

if 'REDIS_URL' in os.environ:
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ['REDIS_URL'],
        'TIMEOUT': 3600,
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
WHITENOISE_AUTOREFRESH = DEBUG
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework with Custom Pagination, Exception Handling, Throttling & JWT Authentication
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'apps.users.authentication.SBPTokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'apps.common.throttling.SbpAnonRateThrottle',
        'apps.common.throttling.SbpUserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10000/minute' if IS_TESTING else os.environ.get('THROTTLE_ANON_RATE', '120/minute'),
        'user': '10000/minute' if IS_TESTING else os.environ.get('THROTTLE_USER_RATE', '1200/minute'),
        'auth_burst': '10000/minute' if IS_TESTING else os.environ.get('THROTTLE_AUTH_BURST_RATE', '10/minute'),
        'auth_sustained': '10000/hour' if IS_TESTING else os.environ.get('THROTTLE_AUTH_SUSTAINED_RATE', '100/hour'),
        'registration': '10000/hour' if IS_TESTING else os.environ.get('THROTTLE_REGISTRATION_RATE', '20/hour'),
        'financial_mutation': '10000/minute' if IS_TESTING else os.environ.get('THROTTLE_FINANCIAL_RATE', '120/minute'),
        'tenant': '10000/minute' if IS_TESTING else os.environ.get('THROTTLE_TENANT_RATE', '5000/minute'),
    },
    'NUM_PROXIES': 1,
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.CustomPageNumberPagination',
    'EXCEPTION_HANDLER': 'apps.common.exception_handlers.custom_exception_handler',
    'PAGE_SIZE': 50,
}

# Django REST Framework SimpleJWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',

    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'SBP Africa Financial Management System (SBP-FMS) API',
    'DESCRIPTION': 'Enterprise Double-Entry Accounting, Multi-Country Statutory Engine & RBAC API (Zero Django Admin)',
    'VERSION': '3.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'filter': True,  # Enables the live search/filter input box at the top of Swagger UI
        'docExpansion': 'list',  # Automatically expands tags so all endpoints are immediately visible
        'defaultModelsExpandDepth': 1,
        'defaultModelExpandDepth': 1,
        'displayRequestDuration': True,
    },
    'TAGS': [
        {
            'name': 'Organizations & Multi-Tenancy',
            'description': 'Customer tenant registration (with 30-day free trial), tenant lifecycle management (PUT/PATCH update, delete, deactivate, reactivate), team memberships, and superadmin tenant overview.'
        },
        {
            'name': 'Subscription Plans & Billing',
            'description': 'SaaS pricing tiers, subscription plans, Paystack payment initialization & verification, and webhooks.'
        },
    ],
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'apps.common.responses.api_response_postprocessing_hook',
    ],
    'ENUM_NAME_OVERRIDES': {
        'DepreciationMethodEnum': 'apps.assets.models.DepreciationMethod',
        'AssetStatusEnum': 'apps.assets.models.AssetStatus',
        'DepreciationRunStatusEnum': 'apps.assets.models.DepreciationRunStatus',
        'PaymentVoucherStatusEnum': 'apps.payables.models.PaymentVoucherStatus',
        'ExpenseClaimStatusEnum': 'apps.payables.models.ExpenseClaimStatus',
        'MatchStatusEnum': 'apps.payables.models.MatchStatus',
        'ClientInvoiceStatusEnum': 'apps.receivables.models.ClientInvoiceStatus',
        'PaymentReceiptStatusEnum': 'apps.receivables.models.PaymentReceiptStatus',
        'ReconciliationStatusEnum': 'apps.treasury.models.ReconciliationStatus',
        'PayrollBatchStatusEnum': 'apps.payroll_escrow.models.PayrollBatchStatus',
        'ContractStatusEnum': 'apps.contracts.models.ContractStatus',
        'BudgetStatusEnum': 'apps.budgeting.models.BudgetStatus',
        'JournalEntryStatusEnum': 'apps.ledger.models.JournalEntryStatus',
        'SubscriptionPlanTierEnum': 'apps.organizations.models.SubscriptionPlanTier',
        'BillingIntervalEnum': 'apps.organizations.models.BillingInterval',
        'TransactionStatusEnum': 'apps.organizations.models.TransactionStatus',
        'OrganizationRoleEnum': 'apps.organizations.models.OrganizationRole',
    },
}

CORS_ALLOW_ALL_ORIGINS = bool(int(os.environ.get('CORS_ALLOW_ALL_ORIGINS', '1' if DEBUG else '0')))
cors_allowed = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if cors_allowed:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_allowed.split(',') if o.strip()]

CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TIMEZONE = 'UTC'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_ALWAYS_EAGER = bool(int(os.environ.get('CELERY_ALWAYS_EAGER', '1' if DEBUG else '0')))
CELERY_TASK_EAGER_PROPAGATES = True

# Celery Beat Periodic Task Schedules
CELERY_BEAT_SCHEDULE = {
    'sync-active-bank-feeds-every-hour': {
        'task': 'apps.treasury.tasks.sync_active_bank_feeds_task',
        'schedule': 3600.0,  # hourly
    },
    'check-overdue-invoices-daily': {
        'task': 'apps.receivables.tasks.check_overdue_invoices_and_send_reminders_task',
        'schedule': 86400.0,  # daily
    },
    'cleanup-expired-tokens-daily': {
        'task': 'apps.common.tasks.cleanup_expired_tokens_and_invitations_task',
        'schedule': 86400.0,  # daily
    },
}

# ============================================================================
# EMAIL BACKEND CONFIGURATION
# ============================================================================
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1').strip().lower() in ('1', 'true', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'SBP Africa Accounting <notifications@sbp-africa.com>')

# ============================================================================
# PAYSTACK PAYMENT GATEWAY CONFIGURATION
# ============================================================================
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_mock_paystack_secret_key')
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'pk_test_mock_paystack_public_key')
PAYSTACK_BASE_URL = os.environ.get('PAYSTACK_BASE_URL', 'https://api.paystack.co')

# ============================================================================
# MONO OPEN BANKING CONFIGURATION (AFRICAN COMMERCIAL BANKS)
# ============================================================================
MONO_SECRET_KEY = os.environ.get('MONO_SECRET_KEY', 'sec_test_mock_mono_secret_key')
MONO_PUBLIC_KEY = os.environ.get('MONO_PUBLIC_KEY', 'pub_test_mock_mono_public_key')
MONO_BASE_URL = os.environ.get('MONO_BASE_URL', 'https://api.withmono.com/v2')

# ============================================================================
# GROQ AI FOREIGN EXCHANGE INTELLIGENCE CONFIGURATION
# ============================================================================
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', 'gsk_mock_test_groq_api_key')
GROQ_BASE_URL = os.environ.get('GROQ_BASE_URL', 'https://api.groq.com/openai/v1').rstrip('/')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
FX_CACHE_TIMEOUT_SECONDS = int(os.environ.get('FX_CACHE_TIMEOUT_SECONDS', '600'))  # 10 minutes cache

# ============================================================================
# PRODUCTION SECURITY & HEADERS
# ============================================================================
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = bool(int(os.environ.get('SECURE_SSL_REDIRECT', '1')))
    SESSION_COOKIE_SECURE = bool(int(os.environ.get('SESSION_COOKIE_SECURE', '1')))
    CSRF_COOKIE_SECURE = bool(int(os.environ.get('CSRF_COOKIE_SECURE', '1')))
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(int(os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', '1')))
    SECURE_HSTS_PRELOAD = bool(int(os.environ.get('SECURE_HSTS_PRELOAD', '1')))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

# ============================================================================
# STRUCTURED PRODUCTION LOGGING
# ============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ==============================================================================
# JAZZMIN MODERN DASHBOARD & ADMIN THEME CONFIGURATION
# ==============================================================================
JAZZMIN_SETTINGS = {
    "site_title": "SBP-FMS Portal",
    "site_header": "SBP Financial Management",
    "site_brand": "SBP-FMS",
    "site_logo_classes": "img-circle",
    "welcome_sign": "Welcome to SBP-FMS Central Administration",
    "copyright": "SBP Africa Group",
    "search_model": "users.User",
    "user_avatar": None,

    # Top Menu Navigation Links
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "API Swagger", "url": "/api/docs/", "new_window": True},
        {"name": "ReDoc", "url": "/api/redoc/", "new_window": True},
        {"name": "System Health", "url": "/health/", "new_window": True},
    ],

    # User Dropdown Menu Links
    "usermenu_links": [
        {"name": "Interactive API Docs", "url": "/api/docs/", "icon": "fas fa-book-open", "new_window": True},
    ],

    # Navigation & Sidebar
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "users",
        "organizations",
        "ledger",
        "receivables",
        "payables",
        "payroll_escrow",
        "treasury",
        "taxation",
        "assets",
        "consolidation",
        "budgeting",
        "contracts",
        "auth",
    ],

    # FontAwesome 5 Icons for Apps & Models
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-user-friends",
        "users": "fas fa-user-shield",
        "users.User": "fas fa-user-circle",
        "users.Role": "fas fa-id-badge",
        "users.Permission": "fas fa-key",
        "organizations": "fas fa-city",
        "organizations.Organization": "fas fa-building",
        "organizations.SubscriptionPlan": "fas fa-gem",
        "organizations.SubscriptionTransaction": "fas fa-receipt",
        "organizations.OrganizationMembership": "fas fa-users",
        "organizations.OrganizationInvitation": "fas fa-paper-plane",
        "organizations.PaymentWebhookLog": "fas fa-history",
    },

    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-navy",
    "accent": "accent-primary",
    "navbar": "navbar-navy navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "flatly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
