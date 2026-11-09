"""Local development and protected staging only; production is intentionally gated."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.environ.get("APP_ENV", "development")
if APP_ENV not in {"development", "staging", "test"}:
    raise ImproperlyConfigured("Production activation is not implemented or authorized.")
DEBUG = APP_ENV == "development"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if APP_ENV == "staging":
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in protected server configuration.")
    SECRET_KEY = "local-development-only-never-use-on-a-server"
if APP_ENV == "staging" and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("local-development")):
    raise ImproperlyConfigured(
        "Staging requires a strong, private DJANGO_SECRET_KEY of at least 50 characters."
    )
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
if APP_ENV == "staging" and ("*" in ALLOWED_HOSTS or not os.environ.get("DJANGO_ALLOWED_HOSTS")):
    raise ImproperlyConfigured("Staging requires explicit DJANGO_ALLOWED_HOSTS without a wildcard.")
CSRF_TRUSTED_ORIGINS = [
    s for s in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if s
]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.LocalProxyClientIPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.AccountAccessMiddleware",
    "core.middleware.StagingAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DESIGN_REVIEW_ONLY = os.environ.get("MONKEYDO_DESIGN_ONLY") == "1"
if DESIGN_REVIEW_ONLY and APP_ENV not in {"test", "staging"}:
    raise ImproperlyConfigured("Design-only hosting requires APP_ENV=staging (or isolated tests).")
ROOT_URLCONF = "config.design_preview_urls" if DESIGN_REVIEW_ONLY else "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context.site_context",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "monkeydo"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    if APP_ENV == "staging":
        raise ImproperlyConfigured("Staging requires an isolated PostgreSQL database.")
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local.sqlite3"}
    }
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
    ("brand", BASE_DIR / "docs/brand-assets/originals"),
    ("children", BASE_DIR / "docs/brand-assets/children-originals"),
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/staff/today/"
LOGOUT_REDIRECT_URL = "/"
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = APP_ENV == "staging"
CSRF_COOKIE_SECURE = APP_ENV == "staging"
SECURE_SSL_REDIRECT = APP_ENV == "staging"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Only enable behind the reviewed local reverse proxy, which overwrites this
# header. Gunicorn must not be reachable directly from the Internet.
if os.environ.get("DJANGO_TRUST_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_RESET_TIMEOUT = 60 * 60
DEFAULT_FROM_EMAIL = "bookings@monkeydoplay.com"

# Opt-in functional staging; the frozen design preview stays the default host.
CUSTOMER_TEST_BOOKING = os.environ.get("MONKEYDO_CUSTOMER_TEST_BOOKING") == "1"
if CUSTOMER_TEST_BOOKING and DESIGN_REVIEW_ONLY:
    raise ImproperlyConfigured(
        "Customer testing and frozen design review require separate services."
    )

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
STAGING_EMAIL_RECIPIENTS = tuple(
    x.strip() for x in os.environ.get("MONKEYDO_TEST_EMAIL_RECIPIENTS", "").split(",") if x.strip()
)
if os.environ.get("MONKEYDO_EMAIL_TRANSPORT") == "resend":
    if APP_ENV not in {"staging", "test"} or not RESEND_API_KEY or not STAGING_EMAIL_RECIPIENTS:
        raise ImproperlyConfigured(
            "Resend staging delivery requires protected credentials and an explicit test-recipient allowlist."
        )
    EMAIL_BACKEND = "core.test_email.StagingEmailBackend"
if (
    APP_ENV == "staging"
    and CUSTOMER_TEST_BOOKING
    and EMAIL_BACKEND != "core.test_email.StagingEmailBackend"
):
    raise ImproperlyConfigured(
        "Functional staging requires controlled test email delivery for staff/owner authentication."
    )

TRUST_LOCAL_CLIENT_IP = os.environ.get("MONKEYDO_TRUST_LOCAL_CLIENT_IP") == "1"
if TRUST_LOCAL_CLIENT_IP and os.environ.get("DJANGO_TRUST_PROXY") != "1":
    raise ImproperlyConfigured("Client-IP trust requires the reviewed local reverse proxy.")
