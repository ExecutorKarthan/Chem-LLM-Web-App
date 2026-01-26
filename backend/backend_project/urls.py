# backend_project/urls.py
from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from backend_project.views import frontend
from api import views as api_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # API endpoints
    path("api/puzzles/", api_views.get_puzzles),
    path("api/check-cookie/", api_views.check_cookie),
    path("api/tokenize-key/", api_views.tokenize_key),
    path("api/list-models/", api_views.list_models),
    path("api/test-key/", api_views.test_api_key),
    path("api/csrf/", api_views.get_csrf_token),
    path("api/ask/", api_views.ask_gemini),
    path("api/clear-token/", api_views.clear_token),

    # Explicitly serve assets from React build
    re_path(r'^assets/(?P<path>.*)$', serve, {
        'document_root': settings.BASE_DIR.parent / 'frontend' / 'dist' / 'assets',
    }),

    # Root route -> React
    path("", frontend, name="frontend_root"),

    # SPA fallback: anything not /api, /admin, or /assets
    re_path(r"^(?!api/|admin/|assets/).*$", frontend, name="frontend_catchall"),
]