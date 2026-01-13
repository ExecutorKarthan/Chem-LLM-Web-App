import os
from pathlib import Path
from dotenv import load_dotenv
from corsheaders.defaults import default_headers

############################################
# Environment
############################################
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY not set")

DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

############################################
# Hosts
############################################
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "llmexplorer.engr.wustl.edu",
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
    'http://localhost:8000',
    'http://llmexplorer.engr.wustl.edu:8000',
    'http://localhost:32780',
]

CORS_ALLOW_HEADERS = list(default_headers) + ["X-Token"]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://localhost:32780',  # For local Vite dev server
    'http://llmexplorer.engr.wustl.edu',
]

############################################
# Cache Configuration (REQUIRED for token storage)
############################################
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 5400,  # 90 minutes
    }
}

############################################
# Static files (React build)
############################################
STATIC_URL = "/assets/"

# Use environment variable for static root if set (read-only safe container)
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", "/opt/app/LLM-Web-App/staticfiles"))

# Only include asset-specific directories, not the full dist folder
STATICFILES_DIRS = [
    BASE_DIR / "assets" / "static",
]

# Add dist/assets only if it exists and is different from STATIC_ROOT
DIST_ASSETS = BASE_DIR.parent / "frontend" / "dist" / "assets"
if DIST_ASSETS.exists() and DIST_ASSETS != STATIC_ROOT:
    STATICFILES_DIRS.append(DIST_ASSETS)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

############################################
# Templates (React index.html)
############################################
# FIX: Use dynamic path relative to BASE_DIR instead of hardcoded /opt/app
REACT_BUILD_DIR = BASE_DIR.parent / "frontend" / "dist"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            REACT_BUILD_DIR,  # Dynamic path
        ],
        "APP_DIRS": False,
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
# URLs
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

# Allow HTTP inside container
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
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
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}