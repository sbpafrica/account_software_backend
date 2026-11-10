import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DEBUG', '1').strip().lower() in ('1', 'true', 'yes', 'on')

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
    # Built-in essentials (NO django.contrib.admin since it is disabled)
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
        'DIRS': [],
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

if 'DATABASE_URL' in os.environ:
    import urllib.parse
    url = urllib.parse.urlparse(os.environ['DATABASE_URL'])
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': urllib.parse.unquote(url.path[1:]),
        'USER': urllib.parse.unquote(url.username or ''),
        'PASSWORD': urllib.parse.unquote(url.password or ''),
        'HOST': url.hostname,
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

# REST Framework with Custom Pagination, Exception Handling & JWT Authentication
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'apps.users.authentication.SBPTokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
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
