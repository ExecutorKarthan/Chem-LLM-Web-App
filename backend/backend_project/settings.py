# Import needed modules
import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.asgi import get_asgi_application
from corsheaders.defaults import default_headers

# Load environmental variables from the '.env' file and define them
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG") == "True"

# Define directory pathing
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'assets' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles_collected'
PUZZLE_CODE_DIR = BASE_DIR / "assets/puzzles"
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Define which hosts are permitted
ALLOWED_HOSTS = [
    "llm-web-app-backend.onrender.com",
    "localhost",
    'llmexplorer.engr.wustl.edu',                 
]

# Application definition
INSTALLED_APPS = [
    'corsheaders',
    'rest_framework',
    'api',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Define programs to handle interactions
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Allow CORS to operate depending on origins
CORS_ALLOWED_ORIGINS = [
    "https://llm-web-app-4970.onrender.com",
    "http://localhost:5173",
    "https://llmexplorer.engr.wustl.edu",
]

# Permit the custom header for tokens
CORS_ALLOW_HEADERS = list(default_headers) + [
    "X-Token",  # Add your custom header here (case insensitive)
]

# Allow cookies to be used
CORS_ALLOW_CREDENTIALS = True

# Define trusted origins for cookies
CSRF_TRUSTED_ORIGINS = [
    "https://llm-web-app-4970.onrender.com/", 
    "https://llmexplorer.engr.wustl.edu", 
]

# Defines locations for URL routs and how to render HTML
ROOT_URLCONF = 'backend_project.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Daatabase configureat - not used but expected
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation - not used but expected
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

# Define AGSI_Appication
WSGI_APPLICATION = 'backend_project.wsgi.application'

# Defines language and time settings
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Load static files
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')
application = get_asgi_application()

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Define security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 5400  
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  

# Set Logging for server
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
}
