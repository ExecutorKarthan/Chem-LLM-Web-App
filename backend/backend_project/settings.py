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
    raise RuntimeError("DJANGO_SECRET_KEY not set in .env file")

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
    'http://127.0.0.1:8000',
    'http://localhost:32775',  # Vite dev server
    'https://llmexplorer.engr.wustl.edu',  # HTTPS for production
]

CORS_ALLOW_HEADERS = list(default_headers) + ["X-Token", "X-CSRFToken"]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:32775',
    'https://llmexplorer.engr.wustl.edu',  # HTTPS for production
]

# CSRF Cookie Settings
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_COOKIE_HTTPONLY = False  # Must be False so JavaScript can read it
CSRF_COOKIE_SAMESITE = 'Lax'  # Changed from 'None' - 'Lax' works for same-site and is more compatible
CSRF_COOKIE_SECURE = not DEBUG  # True in production (HTTPS), False in dev (HTTP)

############################################
# Cache Configuration (REQUIRED for token storage)
############################################
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",  # Use in-memory cache instead
    }
}


############################################
# Static files (React build)
############################################
STATIC_URL = "/assets/"

# Use local path, not /opt/app (production container sets this via env var)
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

# Point to React build assets
STATICFILES_DIRS = [
    BASE_DIR / "assets" / "static",  # Puzzle images
]

# Add React dist/assets if it exists
DIST_ASSETS = BASE_DIR.parent / "frontend" / "dist" / "assets"
if DIST_ASSETS.exists() and DIST_ASSETS != STATIC_ROOT:
    STATICFILES_DIRS.append(DIST_ASSETS)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

############################################
# Templates (React index.html)
############################################
REACT_BUILD_DIR = BASE_DIR.parent / "frontend" / "dist"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            REACT_BUILD_DIR,  # Serve React index.html
        ],
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

# Cookie security (HTTP for development, HTTPS for production)
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