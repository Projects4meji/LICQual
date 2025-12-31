from pathlib import Path
from decouple import Config, RepositoryEnv, Csv

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Pointing to the .env file in the base directory
config = Config(RepositoryEnv(str(BASE_DIR / '.env')))

# Reading environment variables from the .env file
ENV = config("ENV", default="dev")
DEBUG = config("DEBUG", cast=bool, default=True)

# ALLOWED_HOSTS should be defined here only
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

SECRET_KEY = config('SECRET_KEY', default=None)
if not SECRET_KEY:
    if ENV == "prod":
        raise RuntimeError("SECRET_KEY must be set in production via environment")
    # Dev-only fallback
    SECRET_KEY = 'dev-insecure-key-for-local-only'

# No need to redefine ALLOWED_HOSTS again. The value above will be used.
if DEBUG:
    # You can leave ALLOWED_HOSTS as is when DEBUG is True (if you want it to be empty)
    pass
else:
    # You can use additional logic here for production if needed
    pass

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "users.apps.UsersConfig",
    'superadmin.apps.SuperadminConfig',
    "learners",
    "pricing",
    "captcha",

]
if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
# Insert Debug Toolbar middleware right after SecurityMiddleware
if DEBUG:
    try:
        _idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1
    except ValueError:
        _idx = 0
    MIDDLEWARE.insert(_idx, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1', '::1']

ROOT_URLCONF = 'main.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # <— add this so base.html is found
        "APP_DIRS": True,                   # <— keeps app-level templates (users/templates/users)
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "superadmin.context_processors.stripe_context",
                "superadmin.context_processors.business_sidebar_context",
            ],
        },
    },
]

WSGI_APPLICATION = 'main.wsgi.application'

AUTH_USER_MODEL = "users.CustomUser"
STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Where collectstatic will COPY files for production
# Create this folder if it doesn't exist: BASE_DIR / "staticfiles"
STATIC_ROOT = BASE_DIR / "staticfiles"
# settings.py
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# --- Auth redirects (optional but nice defaults) ---
LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "users:user_dashboard"     # or wherever you want after login
LOGOUT_REDIRECT_URL = "users:login"

# Database configuration - use SQLite for local dev if DB_NAME not set
DB_NAME = config('DB_NAME', default=None)
if DB_NAME and ENV != 'dev':
    # Use PostgreSQL for production or when explicitly configured
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': config('DB_USER', default='doadmin'),
            'PASSWORD': config('DB_PASSWORD', default=None),
            'HOST': config('DB_HOST', default='db-licqual-do-user-28152037-0.j.db.ondigitalocean.com'),
            'PORT': config('DB_PORT', default='25060'),
            'OPTIONS': {
                'sslmode': 'require',
            },
        }
    }
else:
    # Use SQLite for local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Email backend (Amazon SES via your backend)
# Use console backend for development when AWS credentials are not configured
USE_SES = config('USE_SES', cast=bool, default=False)
AWS_SES_ACCESS_KEY_ID = config('AWS_SES_ACCESS_KEY_ID', default=None)
AWS_SES_SECRET_ACCESS_KEY = config('AWS_SES_SECRET_ACCESS_KEY', default=None)

if USE_SES and AWS_SES_ACCESS_KEY_ID and AWS_SES_SECRET_ACCESS_KEY:
    # Use SES backend when explicitly enabled and credentials are provided
    EMAIL_BACKEND = 'users.email_backends.SESEmailBackend'
elif DEBUG:
    # Use readable console backend for local development (emails print in readable format)
    EMAIL_BACKEND = 'users.email_backends.ReadableConsoleEmailBackend'
else:
    # Fallback to readable console backend if SES not configured
    EMAIL_BACKEND = 'users.email_backends.ReadableConsoleEmailBackend'

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Licqual@licqual.co.uk')


# Required by forgot/reset flow (seconds)
PASSWORD_RESET_TIMEOUT = config('PASSWORD_RESET_TIMEOUT', cast=int, default=3600)  # 1 hour

# Optional for absolute URLs in emails
SITE_URL = config('SITE_URL', default='http://127.0.0.1:8000')

# Optional: public logo URL for emails if you prefer not to inline

# Stripe Configuration
# Test keys (used when DEBUG=True)
STRIPE_TEST_PUBLISHABLE_KEY = config('STRIPE_TEST_PUBLISHABLE_KEY', default='')
STRIPE_TEST_SECRET_KEY = config('STRIPE_TEST_SECRET_KEY', default='')
STRIPE_TEST_WEBHOOK_SECRET = config('STRIPE_TEST_WEBHOOK_SECRET', default='')

# Live keys (used when DEBUG=False)
STRIPE_LIVE_PUBLISHABLE_KEY = config('STRIPE_LIVE_PUBLISHABLE_KEY', default='')
STRIPE_LIVE_SECRET_KEY = config('STRIPE_LIVE_SECRET_KEY', default='')
STRIPE_LIVE_WEBHOOK_SECRET = config('STRIPE_LIVE_WEBHOOK_SECRET', default='')

# Legacy keys (fallback for existing .env files)
STRIPE_LEGACY_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_LEGACY_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_LEGACY_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# Dynamic Stripe configuration based on DEBUG mode
if DEBUG:
    # Use test keys if available, otherwise fall back to legacy keys
    STRIPE_PUBLISHABLE_KEY = STRIPE_TEST_PUBLISHABLE_KEY or STRIPE_LEGACY_PUBLISHABLE_KEY
    STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY or STRIPE_LEGACY_SECRET_KEY
    STRIPE_WEBHOOK_SECRET = STRIPE_TEST_WEBHOOK_SECRET or STRIPE_LEGACY_WEBHOOK_SECRET
else:
    # Use live keys if available, otherwise fall back to legacy keys
    STRIPE_PUBLISHABLE_KEY = STRIPE_LIVE_PUBLISHABLE_KEY or STRIPE_LEGACY_PUBLISHABLE_KEY
    STRIPE_SECRET_KEY = STRIPE_LIVE_SECRET_KEY or STRIPE_LEGACY_SECRET_KEY
    STRIPE_WEBHOOK_SECRET = STRIPE_LIVE_WEBHOOK_SECRET or STRIPE_LEGACY_WEBHOOK_SECRET
EMAIL_LOGO_URL = config('EMAIL_LOGO_URL', default='')

# Google reCAPTCHA v2 Checkbox keys
RECAPTCHA_PUBLIC_KEY  = config('RECAPTCHA_PUBLIC_KEY', default='')
RECAPTCHA_PRIVATE_KEY = config('RECAPTCHA_PRIVATE_KEY', default='')

# Use Google test keys automatically during local development
if DEBUG and not (RECAPTCHA_PUBLIC_KEY and RECAPTCHA_PRIVATE_KEY):
    RECAPTCHA_PUBLIC_KEY  = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'
    RECAPTCHA_PRIVATE_KEY = '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe'



CERTIFICATE_FONT_PATH = str(BASE_DIR / "static" / "fonts" / "Inter-SemiBold.ttf")


# Celery core settings
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"




# Set the maximum upload size in bytes (50 MB in this case)
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 50 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 50 MB


USE_REMOTE_MEDIA = config("USE_REMOTE_MEDIA", cast=bool, default=False)

if USE_REMOTE_MEDIA:
    INSTALLED_APPS += ["storages"]

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }



    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_BUCKET_NAME = AWS_STORAGE_BUCKET_NAME


    # Region (lower-case, e.g. 'sfo3')
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="sfo3").lower()

    # IMPORTANT: endpoint must be REGION-ONLY, not 'bucket.region...'
    # If your .env mistakenly has 'acsgp.sfo3.digitaloceanspaces.com',
    # we normalize it back to 'sfo3.digitaloceanspaces.com' here.
    _raw_endpoint = config("AWS_S3_ENDPOINT_URL", default=f"https://{AWS_S3_REGION_NAME}.digitaloceanspaces.com")
    from urllib.parse import urlparse
    _eh = urlparse(_raw_endpoint).netloc  # host
    if _eh.endswith(".digitaloceanspaces.com") and _eh.count(".") >= 2:
        # e.g. 'acsgp.sfo3.digitaloceanspaces.com' -> 'sfo3.digitaloceanspaces.com'
        _parts = _eh.split(".")
        if len(_parts) >= 3:
            _eh = ".".join(_parts[-3:])  # keep 'sfo3.digitaloceanspaces.com'
    AWS_S3_ENDPOINT_URL = f"https://{_eh}"

    # Public host to serve files from (bucket.host)
    AWS_S3_CUSTOM_DOMAIN = config(
        "AWS_S3_CUSTOM_DOMAIN",
        default=f"{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_REGION_NAME}.digitaloceanspaces.com",
    )

    # Media URLs should point to your Space host
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

    # Sane defaults for DO Spaces
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = "public-read"   # or None with object params ACL if you want private
    AWS_S3_ADDRESSING_STYLE = "virtual"
    AWS_S3_SIGNATURE_VERSION = "s3v4"