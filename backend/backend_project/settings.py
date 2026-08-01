"""
Django settings for backend_project.

This backend does double duty: it's both the REST API (api/views.py)
and the static-file server for the built React SPA (see the Static
files / Templates sections below, and backend_project.views.frontend) —
there's no separate frontend web server in production, Django/Gunicorn
+ WhiteNoise serves everything.

NOTE: the two print() statements just below run on every process start
(including every Gunicorn worker) — logging.info would be more
consistent with the rest of the app's logging setup (see the LOGGING
section at the bottom), but these are harmless as-is.
"""
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
        "Copy backend/backend_project/.env.template to .env and fill it in."
    )

DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

############################################
# Hosts
# ──────────────────────────────────────────
############################################

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "chem-llm-web-app.onrender.com",
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
]
# NOTE: "32775" is whatever port Vite happened to pick last — Vite's
# default dev port is actually 5173, and it auto-increments to the next
# free port if that's taken. If your local Vite dev server starts on a
# different port than 32775, CORS requests from it will be rejected
# until this list (and the matching entry in CSRF_TRUSTED_ORIGINS
# below) is updated to match.

CORS_ALLOW_HEADERS = list(default_headers) + ["X-Token", "X-CSRFToken"]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:32775",
]

# CSRF Cookie Settings
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False        # Must be False so JavaScript can read it
CSRF_COOKIE_SAMESITE = "Lax"       # Lax is consistent with tokenize_key in views.py
CSRF_COOKIE_SECURE = not DEBUG      # True in production (HTTPS), False in dev (HTTP)

############################################
# Cache
# File-based cache so tokens survive Gunicorn worker restarts.
# LocMemCache is per-process and loses all tokens if a worker dies.
# File cache persists across worker restarts and is safe for single-server use.
############################################
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get("DJANGO_CACHE_DIR", "/tmp/django_cache"),
    }
}

############################################
# Static files (React build output)
############################################
STATIC_URL = "/assets/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

STATICFILES_DIRS = [
    BASE_DIR / "assets" / "static",
]

DIST_ASSETS = BASE_DIR.parent / "frontend" / "dist" / "assets"
if DIST_ASSETS.exists() and DIST_ASSETS != STATIC_ROOT:
    # Only add the raw Vite build output as a source directory if it's
    # actually present (it won't be, e.g., in a backend-only checkout
    # or before `npm run build` has been run) and isn't the same path
    # `collectstatic` already writes to (STATIC_ROOT) — avoiding that
    # would have Django trying to collect a directory from itself.
    STATICFILES_DIRS.append(DIST_ASSETS)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

############################################
# Templates (React index.html served by Django)
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
# Database (SQLite — only used for Django
# internals like sessions; app has no DB needs)
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

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 5400
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False

############################################
# Logging
############################################
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[{asctime}] {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        # This line explicitly silences the file-watcher tracking spam:
        'django.utils.autoreload': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Keeps server requests clean
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}