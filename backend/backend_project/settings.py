import os
from pathlib import Path
from dotenv import load_dotenv
from corsheaders.defaults import default_headers


BASE_DIR = Path(__file__).resolve().parent.parent
print("Base directory for settings:", BASE_DIR)

############################################
# Environment
############################################
print("Loading environment variables from .env file at:", BASE_DIR / "backend_project" / ".env")
load_dotenv(BASE_DIR / "backend_project" / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY not set. "
        "Check that shared/.env exists and is symlinked into the release."
    )

DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

############################################
# Hosts
# !! REPLACE YOUR_SUBDOMAIN once confirmed with WashU IT !!
############################################
PRODUCTION_DOMAIN = os.getenv("PRODUCTION_DOMAIN", "YOUR_SUBDOMAIN.chemistry.wustl.edu")

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    PRODUCTION_DOMAIN,
]

############################################
# Applications
############################################
INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "api",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

############################################
# Middleware
############################################
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

############################################
# CORS / CSRF
############################################
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:32775",
    f"https://{PRODUCTION_DOMAIN}",
]

CORS_ALLOW_HEADERS = list(default_headers) + ["X-Token", "X-CSRFToken"]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:32775",
    f"https://{PRODUCTION_DOMAIN}",
]

CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG

############################################
# Cache
############################################
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

############################################
# Static files
############################################
STATIC_URL = "/assets/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

STATICFILES_DIRS = [
    BASE_DIR / "assets" / "static",
]

DIST_ASSETS = BASE_DIR.parent / "frontend" / "dist" / "assets"
if DIST_ASSETS.exists() and DIST_ASSETS != STATIC_ROOT:
    STATICFILES_DIRS.append(DIST_ASSETS)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

############################################
# Templates
############################################
REACT_BUILD_DIR = BASE_DIR.parent / "frontend" / "dist"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [REACT_BUILD_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

############################################
# URLs / WSGI
############################################
ROOT_URLCONF = "backend_project.urls"
WSGI_APPLICATION = "backend_project.wsgi.application"

############################################
# Database
############################################
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

############################################
# Internationalization
############################################
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

############################################
# Security
############################################
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 5400
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

############################################
# Logging
############################################
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}