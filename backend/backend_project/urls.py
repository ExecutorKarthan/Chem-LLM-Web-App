# backend_project/urls.py
from django.contrib import admin
from django.urls import path, re_path
from backend_project.views import frontend
from api import views as api_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # API endpoints
    path("api/puzzles/", api_views.get_puzzles),
    path("api/check-cookie/", api_views.check_cookie),
    path("api/tokenize-key/", api_views.tokenize_key),
    path("api/list-models/", api_views.list_models),  # ← Add this line
    path("api/ask/", api_views.ask_gemini),
    path("api/clear-token/", api_views.clear_token),

    # Root route -> React
    path("", frontend, name="frontend_root"),

    # SPA fallback: anything not /api or /admin
    re_path(r"^(?!api/|admin/).*$", frontend, name="frontend_catchall"),
]
