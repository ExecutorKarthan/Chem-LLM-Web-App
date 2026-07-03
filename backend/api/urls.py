# backend_project/urls.py
from django.contrib import admin
from django.urls import path, re_path
from backend_project.views import frontend
from api import views as api_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # API endpoints
    path("api/check-cookie/", api_views.check_cookie),
    path("api/tokenize/", api_views.tokenize_key),
    path("api/ask/", api_views.ask_gemini),
    path("api/prime/", api_views.prime_gemini),
    path("api/ask-with-data/", api_views.ask_gemini_with_data),
    path("api/clear-token/", api_views.clear_token),
    path('api/test-key/', api_views.test_api_key, name='test_key'),

    # MOF engine
    path("api/mof-meta/", api_views.get_mof_meta),
    path("api/mof-filter/", api_views.filter_mofs),
    
    path("api/mof-generate/", api_views.generate_mof_code),
    path("api/mof-engine/<str:filename>", api_views.get_mof_engine_file),

    # Root route -> React
    path("", frontend),

    # SPA fallback: anything not /api or /admin
    re_path(r"^(?!api/|admin/).*", frontend),
]