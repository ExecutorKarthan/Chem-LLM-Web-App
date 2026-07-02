# backend_project/urls.py
from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from backend_project.views import frontend
from api import views as api_views

# Root of the React dist folder — used for top-level static files
# like RDKit_minimal.wasm that sit outside the /assets/ prefix.
DIST_ROOT = settings.BASE_DIR.parent / "frontend" / "dist"

urlpatterns = [
    path("admin/", admin.site.urls),

    # ── API endpoints ──────────────────────────────────────────────────────
    path("api/check-cookie/", api_views.check_cookie),
    path("api/tokenize-key/", api_views.tokenize_key),
    path("api/list-models/", api_views.list_models),
    path("api/test-key/", api_views.test_api_key),
    path("api/csrf/", api_views.get_csrf_token),
    path("api/ask/", api_views.ask_gemini),
    path("api/prime/", api_views.prime_gemini),
    path("api/ask-with-data/", api_views.ask_gemini_with_data),
    path("api/clear-token/", api_views.clear_token),
    path("api/mof-generate/", api_views.generate_mof_code),
    path("api/mof-engine/<str:filename>", api_views.get_mof_engine_file),

    # ── RDKit WASM — must be explicit BEFORE the SPA catchall ─────────────
    # The catchall regex below would intercept /RDKit_minimal.wasm and return
    # index.html, which causes the "expected magic word 00 61 73 6d, found
    # 3c 21 2d 2d" error (Django is returning HTML instead of binary WASM).
    path(
        "RDKit_minimal.wasm",
        serve,
        {"document_root": DIST_ROOT, "path": "RDKit_minimal.wasm"},
    ),

    # ── React build assets (/assets/...) ───────────────────────────────────
    re_path(
        r"^assets/(?P<path>.*)$",
        serve,
        {"document_root": DIST_ROOT / "assets"},
    ),

    # ── Root route → React ─────────────────────────────────────────────────
    path("", frontend, name="frontend_root"),

    # ── SPA fallback — anything not matched above → React index.html ───────
    re_path(r"^(?!api/|admin/|assets/).*$", frontend, name="frontend_catchall"),
]