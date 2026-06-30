# Standard library imports
import time
import os
import uuid
import json
import logging
import csv
from pathlib import Path

# Django / DRF imports
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.cache import cache
from django.middleware.csrf import get_token

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Google Gemini SDK
from google import genai
from google.genai.errors import ClientError, ServerError

# HTTP client (for catching low-level connection errors from Gemini)
import httpx

# Set up logger
logger = logging.getLogger(__name__)


############################################
# CSRF Token endpoint
############################################
@ensure_csrf_cookie
def get_csrf_token(request):
    """Return CSRF token for frontend"""
    token = get_token(request)
    logger.info(f"[CSRF] Generated CSRF token: {token[:10]}...")
    response = JsonResponse({'csrfToken': token})
    return response


############################################
# Cookie existence check
############################################
def check_cookie(request):
    logger.info("=" * 80)
    logger.info("[CHECK_COOKIE] Checking for gemini_token cookie")

    all_cookies = request.COOKIES
    logger.info(f"[CHECK_COOKIE] All cookies present: {list(all_cookies.keys())}")

    token = request.COOKIES.get("gemini_token")
    logger.info(f"[CHECK_COOKIE] gemini_token exists: {bool(token)}")
    if token:
        logger.info(f"[CHECK_COOKIE] Token value: {token}")
        cached_value = cache.get(token)
        logger.info(f"[CHECK_COOKIE] Token found in cache: {cached_value is not None}")
        if cached_value:
            logger.info(f"[CHECK_COOKIE] Cached API key length: {len(cached_value)}")
            logger.info(f"[CHECK_COOKIE] Cached API key preview: {cached_value[:10]}...")

    logger.info("=" * 80)
    return JsonResponse({"token_exists": bool(token)})


############################################
# Tokenize API key into cache + secure cookie
############################################
@csrf_exempt
@ensure_csrf_cookie
def tokenize_key(request):
    logger.info("=" * 80)
    logger.info("[TOKENIZE] Starting tokenization process")
    logger.info(f"[TOKENIZE] Request method: {request.method}")

    if request.method != "POST":
        logger.error(f"[TOKENIZE] Invalid method: {request.method}")
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        body = json.loads(request.body)
        api_key = body.get("apiKey")
        logger.info(f"[TOKENIZE] API key received: {api_key is not None}")

        if not api_key:
            logger.error("[TOKENIZE] No API key provided")
            return JsonResponse({"error": "API key is required"}, status=400)

        api_key = api_key.strip()
        logger.info(f"[TOKENIZE] API key length: {len(api_key)}")
        logger.info(f"[TOKENIZE] API key preview: {api_key[:10]}...")

        token = str(uuid.uuid4())
        logger.info(f"[TOKENIZE] Generated token: {token}")

        # Test cache connection before storing
        try:
            cache.set("test_connection", "test_value", timeout=10)
            test_retrieve = cache.get("test_connection")
            logger.info(f"[TOKENIZE] Cache connection test: {test_retrieve == 'test_value'}")
            cache.delete("test_connection")
        except Exception as cache_err:
            logger.error(f"[TOKENIZE] Cache connection test FAILED: {cache_err}")
            return JsonResponse(
                {"error": "Cache connection failed", "details": str(cache_err)},
                status=500,
            )

        cache.set(token, api_key, timeout=5400)
        logger.info("[TOKENIZE] Storage complete")

        retrieved = cache.get(token)
        logger.info(f"[TOKENIZE] Verification - Retrieved from cache: {retrieved is not None}")
        if retrieved:
            logger.info(f"[TOKENIZE] Verification - Keys match: {retrieved == api_key}")
        else:
            logger.error("[TOKENIZE] CRITICAL: Failed to retrieve from cache after storage!")
            return JsonResponse({"error": "Failed to store token in cache"}, status=500)

        # secure=True in production (HTTPS), False in dev (HTTP)
        is_secure = not settings.DEBUG

        response = JsonResponse({"message": "Token set in secure cookie."})
        response.set_cookie(
            key="gemini_token",
            value=token,
            max_age=5400,
            secure=is_secure,
            httponly=True,
            # "Lax" is consistent with CSRF_COOKIE_SAMESITE in settings.py.
            # The original "None" caused a dev/prod mismatch and required
            # secure=True unconditionally (which breaks HTTP dev environments).
            samesite="Lax",
            path="/",
        )
        logger.info("[TOKENIZE] Cookie set in response")
        logger.info("=" * 80)
        return response

    except Exception as e:
        logger.error(f"[TOKENIZE] ERROR: {e}", exc_info=True)
        return JsonResponse({"error": "Server error", "details": str(e)}, status=500)


############################################
# List available models (DEBUG)
############################################
@csrf_exempt
@api_view(["GET"])
def list_models(request):
    """Debug endpoint to list available Gemini models"""
    logger.info("=" * 80)
    logger.info("[LIST_MODELS] Request received")

    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response({"error": "No token"}, status=401)

    api_key = cache.get(token)
    if not api_key:
        return Response({"error": "Invalid token"}, status=403)

    try:
        client = genai.Client(api_key=api_key)
        models = client.models.list()
        model_names = [model.name for model in models]
        logger.info(f"[LIST_MODELS] Found {len(model_names)} models")
        logger.info("=" * 80)
        return Response({"models": model_names})
    except Exception as e:
        logger.error(f"[LIST_MODELS] Error: {e}", exc_info=True)
        logger.info("=" * 80)
        return Response({"error": str(e)}, status=500)


############################################
# Test API key (DEBUG)
############################################
@csrf_exempt
@api_view(["GET"])
def test_api_key(request):
    """Debug endpoint to test if the stored API key works"""
    logger.info("=" * 80)
    logger.info("[TEST_KEY] Request received")

    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response({"error": "No token"}, status=401)

    api_key = cache.get(token)
    if not api_key:
        return Response({"error": "Invalid token"}, status=403)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello",
        )
        logger.info("[TEST_KEY] API key works!")
        logger.info("=" * 80)
        return Response({"success": True, "api_key_works": True, "response": response.text})
    except Exception as e:
        logger.error(f"[TEST_KEY] Error: {e}", exc_info=True)
        logger.info("=" * 80)
        return Response({"success": False, "error": str(e), "error_type": type(e).__name__}, status=400)


############################################
# Gemini query endpoint
############################################
@csrf_exempt
@api_view(["POST"])
def ask_gemini(request, max_retries=2, delay=2):
    logger.info("=" * 80)
    logger.info("[ASK_GEMINI] ========== NEW REQUEST ==========")

    model_names = [
        "gemini-2.5-flash",       # stable, fast, generous quota -- try first
        "gemini-2.5-flash-lite",  # stable, lightweight fallback
        "gemini-2.5-pro",         # stable, most capable
        "gemini-3-flash-preview", # preview -- unreliable, last resort
        "gemini-3-pro-preview",   # preview -- unreliable, last resort
    ]

    token = request.COOKIES.get("gemini_token")
    if not token:
        logger.error("[ASK_GEMINI] FAILURE: No gemini_token cookie present")
        logger.info("=" * 80)
        return Response({"error": "Missing gemini_token cookie."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        api_key = cache.get(token)
    except Exception as cache_error:
        logger.error(f"[ASK_GEMINI] Cache error: {cache_error}", exc_info=True)
        logger.info("=" * 80)
        return Response({"error": f"Cache error: {str(cache_error)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if not api_key:
        logger.error("[ASK_GEMINI] FAILURE: Token not found in cache")
        logger.info("=" * 80)
        return Response({"error": "Invalid or expired token."}, status=status.HTTP_403_FORBIDDEN)

    prompt = request.data.get("prompt")
    if not prompt:
        logger.error("[ASK_GEMINI] FAILURE: No prompt in request")
        logger.info("=" * 80)
        return Response({"error": "Prompt is missing in request."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[ASK_GEMINI] Failed to create Gemini client: {e}", exc_info=True)
        logger.info("=" * 80)
        return Response({"error": f"Failed to create Gemini client: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                logger.info(f"[ASK_GEMINI] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(model=model_name, contents=prompt)
                response_text = response.text if response.text is not None else ""
                logger.info(f"[ASK_GEMINI] SUCCESS with {model_name}. Response length: {len(response_text)}")
                logger.info("=" * 80)
                return Response({"response": response_text}, status=status.HTTP_200_OK)

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[ASK_GEMINI] ClientError with {model_name}: {error_message}")
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    logger.error("[ASK_GEMINI] FAILURE: Invalid API key")
                    logger.info("=" * 80)
                    return Response({"error": "Invalid or unauthorized API key provided."}, status=status.HTTP_401_UNAUTHORIZED)
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    logger.warning(f"[ASK_GEMINI] {model_name} quota exceeded, trying next model...")
                    break
                logger.info("=" * 80)
                return Response({"error": f"Client error with {model_name}: {error_message}"}, status=status.HTTP_400_BAD_REQUEST)

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[ASK_GEMINI] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue
                logger.error(f"[ASK_GEMINI] ServerError: {e}", exc_info=True)
                logger.info("=" * 80)
                return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                logger.warning(f"[ASK_GEMINI] Network error with {model_name}: {e} — trying next model")
                break  # move to next model
            except Exception as e:
                logger.error(f"[ASK_GEMINI] Unexpected error: {e}", exc_info=True)
                logger.info("=" * 80)
                return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.error("[ASK_GEMINI] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return Response({"error": "All Gemini models are currently unavailable or quota exceeded."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


############################################
# Helper: load MOF CSV as formatted string
############################################
MOF_CSV_PATH = os.path.join(settings.BASE_DIR, "assets", "MOF_data.csv")


def load_mof_csv():
    """
    Reads the MOF CSV from disk and returns a formatted string
    suitable for inline injection into a Gemini prompt.
    """
    if not os.path.exists(MOF_CSV_PATH):
        logger.error(f"[MOF_CSV] File not found at: {MOF_CSV_PATH}")
        raise FileNotFoundError(
            f"MOF data file not found at {MOF_CSV_PATH}. "
            "Please ensure MOF_data.csv exists in backend/assets/."
        )

    rows = []
    with open(MOF_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("MOF CSV is empty or has no header row.")
        for row in reader:
            rows.append(row)

    if not rows:
        raise ValueError("MOF CSV has headers but contains no data rows.")

    logger.info(f"[MOF_CSV] Loaded {len(rows)} rows with columns: {headers}")

    lines = ["MOF REFERENCE DATA (SMILES notation):"]
    lines.append(", ".join(headers))
    lines.append("-" * 80)
    for row in rows:
        lines.append(", ".join(str(row.get(h, "")) for h in headers))

    return "\n".join(lines)


############################################
# Prime Gemini with MOF CSV data
############################################
@csrf_exempt
@api_view(["POST"])
def prime_gemini(request, max_retries=2, delay=2):
    """
    Sends the MOF CSV data to Gemini as a standalone priming call.
    Returns Gemini's acknowledgment response, prefaced with a success message.
    """
    logger.info("=" * 80)
    logger.info("[PRIME_GEMINI] ========== NEW PRIME REQUEST ==========")

    try:
        csv_content = load_mof_csv()
    except FileNotFoundError as e:
        logger.error(f"[PRIME_GEMINI] CSV missing: {e}")
        return Response({"error": str(e), "csv_missing": True}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        logger.error(f"[PRIME_GEMINI] CSV invalid: {e}")
        return Response({"error": str(e), "csv_missing": True}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response({"error": "Missing gemini_token cookie."}, status=status.HTTP_401_UNAUTHORIZED)
    api_key = cache.get(token)
    if not api_key:
        return Response({"error": "Invalid or expired token."}, status=status.HTTP_403_FORBIDDEN)

    priming_prompt = (
        "You are a chemistry assistant specialising in Metal-Organic Frameworks (MOFs) "
        "and Covalent Organic Frameworks (COFs). I am providing you with a reference "
        "dataset of MOF molecules in SMILES notation along with their framework "
        "properties. Please acknowledge you have received this data and briefly summarise "
        "what it contains so I know you are ready to answer questions about it.\n\n"
        f"{csv_content}"
    )

    model_names = [
        "gemini-2.5-flash",       # stable, fast, generous quota -- try first
        "gemini-2.5-flash-lite",  # stable, lightweight fallback
        "gemini-2.5-pro",         # stable, most capable
        "gemini-3-flash-preview", # preview -- unreliable, last resort
        "gemini-3-pro-preview",   # preview -- unreliable, last resort
    ]

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[PRIME_GEMINI] Failed to create Gemini client: {e}", exc_info=True)
        return Response({"error": f"Failed to create Gemini client: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                logger.info(f"[PRIME_GEMINI] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(model=model_name, contents=priming_prompt)
                response_text = response.text if response.text is not None else ""
                logger.info(f"[PRIME_GEMINI] SUCCESS with {model_name}")
                logger.info("=" * 80)
                return Response({"response": "✅ MOF data was successfully submitted to Gemini.\n\n" + response_text}, status=status.HTTP_200_OK)

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[PRIME_GEMINI] ClientError with {model_name}: {error_message}")
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    return Response({"error": "Invalid or unauthorized API key provided."}, status=status.HTTP_401_UNAUTHORIZED)
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    logger.warning(f"[PRIME_GEMINI] {model_name} quota exceeded, trying next model...")
                    break
                return Response({"error": f"Client error with {model_name}: {error_message}"}, status=status.HTTP_400_BAD_REQUEST)

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[PRIME_GEMINI] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue
                logger.error(f"[PRIME_GEMINI] ServerError: {e}", exc_info=True)
                return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                logger.warning(f"[PRIME_GEMINI] Network error with {model_name}: {e} — trying next model")
                break  # move to next model
            except Exception as e:
                logger.error(f"[PRIME_GEMINI] Unexpected error: {e}", exc_info=True)
                return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.error("[PRIME_GEMINI] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return Response({"error": "All Gemini models are currently unavailable or quota exceeded."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


############################################
# Gemini query endpoint WITH CSV prepended
############################################
@csrf_exempt
@api_view(["POST"])
def ask_gemini_with_data(request, max_retries=2, delay=2):
    """
    Same as ask_gemini but prepends the full MOF CSV to every prompt
    so Gemini has the reference data available for every question.
    """
    logger.info("=" * 80)
    logger.info("[ASK_GEMINI_WITH_DATA] ========== NEW REQUEST ==========")

    try:
        csv_content = load_mof_csv()
    except FileNotFoundError as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] CSV missing: {e}")
        return Response({"error": str(e), "csv_missing": True}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] CSV invalid: {e}")
        return Response({"error": str(e), "csv_missing": True}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response({"error": "Missing gemini_token cookie."}, status=status.HTTP_401_UNAUTHORIZED)
    api_key = cache.get(token)
    if not api_key:
        return Response({"error": "Invalid or expired token."}, status=status.HTTP_403_FORBIDDEN)

    prompt = request.data.get("prompt")
    if not prompt:
        return Response({"error": "Prompt is missing in request."}, status=status.HTTP_400_BAD_REQUEST)

    full_prompt = (
        "You are a chemistry assistant specialising in MOFs and COFs. "
        "Use the following MOF reference data to answer the user's question.\n\n"
        f"{csv_content}\n\n"
        f"USER QUESTION: {prompt}"
    )

    model_names = [
        "gemini-2.5-flash",       # stable, fast, generous quota -- try first
        "gemini-2.5-flash-lite",  # stable, lightweight fallback
        "gemini-2.5-pro",         # stable, most capable
        "gemini-3-flash-preview", # preview -- unreliable, last resort
        "gemini-3-pro-preview",   # preview -- unreliable, last resort
    ]

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] Failed to create Gemini client: {e}", exc_info=True)
        return Response({"error": f"Failed to create Gemini client: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                logger.info(f"[ASK_GEMINI_WITH_DATA] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(model=model_name, contents=full_prompt)
                response_text = response.text if response.text is not None else ""
                logger.info(f"[ASK_GEMINI_WITH_DATA] SUCCESS with {model_name}")
                logger.info("=" * 80)
                return Response({"response": response_text}, status=status.HTTP_200_OK)

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[ASK_GEMINI_WITH_DATA] ClientError with {model_name}: {error_message}")
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    return Response({"error": "Invalid or unauthorized API key provided."}, status=status.HTTP_401_UNAUTHORIZED)
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    logger.warning(f"[ASK_GEMINI_WITH_DATA] {model_name} quota exceeded, trying next model...")
                    break
                return Response({"error": f"Client error with {model_name}: {error_message}"}, status=status.HTTP_400_BAD_REQUEST)

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[ASK_GEMINI_WITH_DATA] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue
                logger.error(f"[ASK_GEMINI_WITH_DATA] ServerError: {e}", exc_info=True)
                return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                logger.warning(f"[ASK_GEMINI_WITH_DATA] Network error with {model_name}: {e} — trying next model")
                break  # move to next model
            except Exception as e:
                logger.error(f"[ASK_GEMINI_WITH_DATA] Unexpected error: {e}", exc_info=True)
                return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.error("[ASK_GEMINI_WITH_DATA] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return Response({"error": "All Gemini models are currently unavailable or quota exceeded."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


############################################
# Clear token + cookie
############################################
@csrf_exempt
@api_view(["POST"])
def clear_token(request):
    logger.info("=" * 80)
    logger.info("[CLEAR_TOKEN] Request received")

    token = request.COOKIES.get("gemini_token")
    if token:
        cache.delete(token)
        logger.info("[CLEAR_TOKEN] Token deleted from cache")
    else:
        logger.info("[CLEAR_TOKEN] No token to clear")

    response = JsonResponse({"message": "Token cleared."})
    response.delete_cookie("gemini_token", samesite="Lax")
    logger.info("[CLEAR_TOKEN] Cookie deleted from response")
    logger.info("=" * 80)
    return response


############################################
# Serve MOF renderer Python source to Skulpt
# ──────────────────────────────────────────
# Skulpt runs Python in the browser and needs the actual .py source text
# for any module the generated code imports (e.g. `from mof_renderer
# import MOFRenderer`). We keep these files on the backend only — this
# endpoint serves them as plain text by filename, restricted to a fixed
# whitelist so arbitrary file paths can never be requested.
############################################
MOF_ENGINE_DIR = Path(__file__).resolve().parent / "mof_engine"

MOF_ENGINE_WHITELIST = {
    "smiles_lexer.py",
    "smiles_parser.py",
    "ring_utils.py",
    "ring_layout.py",
    "coordination_geometry.py",
    "layout_engine.py",
    "turtle_renderer.py",
    "mof_renderer.py",
}


@api_view(["GET"])
def get_mof_engine_file(request, filename):
    """
    Serve one whitelisted .py source file as plain text.
    Used by the frontend's Skulpt `read()` callback so the browser-side
    Python interpreter can resolve `import` statements in the generated
    MOF-drawing code without the source ever being bundled client-side.
    """
    if filename not in MOF_ENGINE_WHITELIST:
        logger.warning(f"[MOF_ENGINE] Rejected non-whitelisted filename: {filename}")
        return JsonResponse({"error": "File not found"}, status=404)

    file_path = MOF_ENGINE_DIR / filename

    if not file_path.is_file():
        logger.error(f"[MOF_ENGINE] Whitelisted file missing on disk: {file_path}")
        return JsonResponse({"error": "File not found"}, status=404)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"[MOF_ENGINE] Failed to read {filename}: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to read file"}, status=500)

    return HttpResponse(content, content_type="text/plain; charset=utf-8")


############################################
# Serve MOF_data.csv (pore size lookup table)
# ──────────────────────────────────────────
# mof_renderer.py expects MOF_DB to be embedded in its own source, so this
# endpoint isn't required for normal operation — kept here only in case a
# future version of mof_renderer.py is changed to load the CSV at runtime
# instead of embedding it.
############################################
@api_view(["GET"])
def get_mof_data_csv(request):
    csv_path = Path(settings.BASE_DIR) / "assets" / "MOF_data.csv"

    if not csv_path.is_file():
        logger.error(f"[MOF_DATA_CSV] File missing: {csv_path}")
        return JsonResponse({"error": "MOF_data.csv not found", "csv_missing": True}, status=404)

    try:
        content = csv_path.read_text(encoding="utf-8-sig")
    except Exception as e:
        logger.error(f"[MOF_DATA_CSV] Failed to read: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to read MOF_data.csv"}, status=500)

    return HttpResponse(content, content_type="text/csv; charset=utf-8")