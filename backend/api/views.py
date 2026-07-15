# Standard library imports
import time
import os
import re
import uuid
import json
import logging
import csv
from pathlib import Path
from assets import mof_index

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

# Locate assets folder safely relative to backend directory structure
MOF_DATA_CSV_PATH = Path(settings.BASE_DIR) / "assets" / "MOF_data.csv"

# In-memory engine cache for generated module sources
_mof_data_cache = {"mtime": None, "source": None}

# ─────────────────────────────────────────────────────────────────────────────
# ION RADII CHEMICAL SCALING ARCHETYPES
# ─────────────────────────────────────────────────────────────────────────────
ION_RADII = {
    "Li+":  (0.76,  3.40, "Experimentally Verified"),
    "Na+":  (1.02,  3.58, "Experimentally Verified"),
    "K+":   (1.38,  3.31, "Experimentally Verified"),
    "Rb+":  (1.52,  3.29, "Experimentally Verified"),
    "Cs+":  (1.67,  3.29, "Experimentally Verified"),
    "Be2+": (0.45,  4.59, "Estimated / Unverified"),
    "Mg2+": (0.72,  4.28, "Experimentally Verified"),
    "Ca2+": (1.00,  4.12, "Experimentally Verified"),
    "Sr2+": (1.18,  4.12, "Experimentally Verified"),
    "Ba2+": (1.35,  4.04, "Experimentally Verified"),
    "Cu+":  (0.77,  3.20, "Estimated / Unverified"),
    "V2+":  (0.79,  4.30, "Estimated / Unverified"),
    "Cr2+": (0.73,  4.25, "Estimated / Unverified"),
    "Mn2+": (0.67,  4.38, "Experimentally Verified"),
    "Fe2+": (0.61,  4.28, "Experimentally Verified"),
    "Co2+": (0.65,  4.23, "Experimentally Verified"),
    "Ni2+": (0.69,  4.04, "Experimentally Verified"),
    "Cu2+": (0.73,  4.19, "Experimentally Verified"),
    "Zn2+": (0.74,  4.30, "Experimentally Verified"),
    "Ti2+": (0.86,  4.35, "Estimated / Unverified"),
    "Sn2+": (1.12,  3.95, "Estimated / Unverified"),
    "Pb2+": (1.19,  4.01, "Estimated / Unverified"),
    "Ti3+": (0.67,  4.65, "Estimated / Unverified"),
    "V3+":  (0.64,  4.60, "Estimated / Unverified"),
    "Cr3+": (0.62,  4.61, "Estimated / Unverified"),
    "Mn3+": (0.58,  4.60, "Estimated / Unverified"),
    "Fe3+": (0.55,  4.57, "Experimentally Verified"),
    "Co3+": (0.55,  4.55, "Estimated / Unverified"),
    "Ti4+": (0.61,  4.70, "Estimated / Unverified"),
    "V4+":  (0.58,  4.70, "Estimated / Unverified"),
    "Mn4+": (0.53,  4.75, "Estimated / Unverified"),
    "V5+":  (0.54,  4.80, "Estimated / Unverified"),
    "Cr6+": (0.44,  4.90, "Estimated / Unverified"),
    "Mn7+": (0.46,  4.90, "Estimated / Unverified"),
    "Al3+": (0.54,  4.75, "Experimentally Verified"),
    "Ga3+": (0.62,  4.65, "Estimated / Unverified"),
    "In3+": (0.80,  4.63, "Estimated / Unverified"),
    "Sn4+": (0.69,  4.65, "Estimated / Unverified"),
    "Pb4+": (0.78,  4.60, "Estimated / Unverified"),
    "Sc3+": (0.75,  4.50, "Experimentally Verified"),
    "Y3+":  (0.90,  4.40, "Experimentally Verified"),
    "La3+": (1.03,  4.52, "Experimentally Verified"),
    "Ce3+": (1.01,  4.51, "Estimated / Unverified"),
    "Ce4+": (0.87,  4.65, "Estimated / Unverified"),
    "Nd3+": (0.98,  4.48, "Estimated / Unverified"),
    "Gd3+": (0.94,  4.45, "Estimated / Unverified"),
    "Lu3+": (0.86,  4.39, "Estimated / Unverified"),
    "U3+":  (1.03,  4.73, "Estimated / Unverified"),
    "U4+":  (0.89,  4.83, "Estimated / Unverified"),
    "U6+":  (0.73,  4.85, "Estimated / Unverified"),
    "Np3+": (1.01,  4.72, "Estimated / Unverified"),
    "Np4+": (0.87,  4.84, "Estimated / Unverified"),
    "Pu3+": (1.00,  4.71, "Estimated / Unverified"),
    "Pu4+": (0.86,  4.82, "Estimated / Unverified"),
    "Am3+": (0.98,  4.70, "Estimated / Unverified"),
    "Am4+": (0.85,  4.80, "Estimated / Unverified"),
    "Ac3+": (1.12,  4.75, "Estimated / Unverified"),
    "Th4+": (0.94,  4.87, "Estimated / Unverified"),
    "Pa4+": (0.90,  4.85, "Estimated / Unverified"),
    "Pa5+": (0.78,  4.90, "Estimated / Unverified"),
}


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

        is_secure = not settings.DEBUG

        response = JsonResponse({"message": "Token set in secure cookie."})
        response.set_cookie(
            key="gemini_token",
            value=token,
            max_age=5400,
            secure=is_secure,
            httponly=True,
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
def load_mof_csv():
    """
    Reads the MOF CSV from disk and returns a formatted string
    suitable for inline injection into a Gemini prompt.
    """
    if not MOF_DATA_CSV_PATH.is_file():
        logger.error(f"[MOF_CSV] File not found at: {MOF_DATA_CSV_PATH}")
        raise FileNotFoundError(
            f"MOF data file not found at {MOF_DATA_CSV_PATH}. "
            "Please ensure MOF_data.csv exists in backend/assets/."
        )

    rows = []
    with MOF_DATA_CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
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
                    logger.warning(f"[ASK_GEMINI] {model_name} unavailable, retrying...")
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
# Dynamic mof_data.py Structural Rebuilder
############################################
def _build_mof_data_source():
    """Read MOF_data.csv from disk and return generated `mof_data.py` source."""
    rows = []
    
    print(f"\n[MOF PARSER] Absolute target path: {MOF_DATA_CSV_PATH.resolve()}")
    print(f"[MOF PARSER] Does the file physically exist here? {MOF_DATA_CSV_PATH.is_file()}")
    
    if not MOF_DATA_CSV_PATH.is_file():
        print("[MOF PARSER] ERROR: Cannot proceed, target file is missing.")
        return ""

    try:
        with MOF_DATA_CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            print(f"[MOF PARSER] CSV successfully opened. Columns found: {headers}")
            
            lcd_key = next((h for h in headers if "Largest Cavity" in h), None)
            pld_key = next((h for h in headers if "Pore Limiting" in h), None)
            id_key = next((h for h in headers if "Identifier" in h), None)
            metal_key = next((h for h in headers if "Metal Types" in h), None)

            if not (lcd_key and pld_key and id_key and metal_key):
                print(f"[MOF PARSER] ERROR: Missing vital header columns! (LCD: {lcd_key}, PLD: {pld_key}, ID: {id_key}, Metal: {metal_key})")
                return ""

            for idx, row in enumerate(reader):
                mof_id = (row.get(id_key) or "").strip()
                metal = (row.get(metal_key) or "").strip()
                
                if not mof_id or not metal:
                    continue
                try:
                    lcd = float(row[lcd_key])
                    pld = float(row[pld_key])
                except (TypeError, ValueError):
                    continue
                rows.append((mof_id, lcd, pld, metal))
                
            print(f"[MOF PARSER] Parsed structural rows count from file: {len(rows)}")
            
    except Exception as e:
        print(f"[MOF PARSER] CRITICAL ERROR during execution loop: {e}")
        return ""

    lines = [
        "# mof_data.py",
        "# AUTO-GENERATED from api/assets/MOF_data.csv — do not edit by hand.",
        "MOF_DB = {",
    ]
    for mof_id, lcd, pld, metal in rows:
        lines.append(f"    {mof_id!r}: ({lcd!r}, {pld!r}, {metal!r}),")
    lines.append("}")
    return "\n".join(lines)


def _mof_data_source_cached():
    if not MOF_DATA_CSV_PATH.is_file():
        raise FileNotFoundError(f"MOF_data.csv not found at {MOF_DATA_CSV_PATH}")
    current_mtime = MOF_DATA_CSV_PATH.stat().st_mtime
    if _mof_data_cache["source"] is None or _mof_data_cache["mtime"] != current_mtime:
        _mof_data_cache["source"] = _build_mof_data_source()
        _mof_data_cache["mtime"] = current_mtime
    return _mof_data_cache["source"]


def _get_parsed_mof_db():
    """Retrieves the database dictionary by evaluating the generated source."""
    try:
        src = _mof_data_source_cached()
        if not src:
            return {}
        local_vars = {}
        exec(src, {}, local_vars)
        return local_vars.get("MOF_DB", {})
    except Exception as e:
        logger.error(f"Failed parsing cached mof data dict: {e}")
        return {}


def _extract_organic_linker(mof_id_smiles):
    """
    Splits a composite multi-component SMILES string by '.' and filters
    out inorganic metal fragments, leaving only the organic linker.
    """
    if not mof_id_smiles:
        return ""
    fragments = mof_id_smiles.split(".")
    organic_fragments = []
    
    metals_list = [
        "Ag", "Zn", "Cu", "Fe", "Co", "Ni", "Al", "Cr", "Zr", "Ti", "In", "Mg", "V", 
        "Sc", "Y", "La", "Ce", "Nd", "Gd", "Lu", "U", "Np", "Pu", "Am", "Ac", "Th", 
        "Pa", "Li", "Na", "K", "Rb", "Cs", "Be", "Ba", "Sr", "Ca", "Sn", "Pb", "Ga"
    ]
    
    for frag in fragments:
        is_metal = any(m in frag for m in metals_list)
        if not is_metal:
            organic_fragments.append(frag)
            
    return ".".join(organic_fragments) if organic_fragments else mof_id_smiles


############################################
# Dynamic Search and Metadata Catalogs
############################################
# Locate your new assets safely
REGISTRY_LINKERS_CSV = Path(settings.BASE_DIR) / "assets" / "registry_by_linkers.csv"
REGISTRY_METALS_CSV = Path(settings.BASE_DIR) / "assets" / "registry_by_metals.csv"

@api_view(["GET"])
def get_mof_meta(request):
    """
    Returns all available metals and all available linkers initially,
    along with guest ions.
    """
    metals = []
    linkers = []
    
    # 1. Load Metals
    if REGISTRY_METALS_CSV.exists():
        with open(REGISTRY_METALS_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                metals.append({
                    "value": row["metal"],
                    "label": row["metal"]
                })
                
    # 2. Load Linkers
    if REGISTRY_LINKERS_CSV.exists():
        with open(REGISTRY_LINKERS_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use common name if available, otherwise fallback to SMILES
                display_name = row["common_name"].strip() if row["common_name"].strip() else row["linker_smiles"]
                linkers.append({
                    "value": row["linker_smiles"],
                    "label": display_name
                })

    guest_ions = [
        "Li+", "Na+", "K+", "Rb+", "Cs+", "Be2+", "Mg2+", "Ca2+", "Sr2+", "Ba2+",
        "Cu+", "V2+", "Cr2+", "Mn2+", "Fe2+", "Co2+", "Ni2+", "Cu2+", "Zn2+", "Ti2+",
        "Sn2+", "Pb2+", "Ti3+", "V3+", "Cr3+", "Mn3+", "Fe3+", "Co3+", "Ti4+", "V4+",
        "Mn4+", "V5+", "Cr6+", "Mn7+", "Al3+", "Ga3+", "In3+", "Sn4+", "Pb4+", "Sc3+",
        "Y3+", "La3+", "Ce3+", "Ce4+", "Nd3+", "Gd3+", "Lu3+", "U3+", "U4+", "U6+",
        "Np3+", "Np4+", "Pu3+", "Pu4+", "Am3+", "Am4+", "Ac3+", "Th4+", "Pa4+", "Pa5+"
    ]
    
    return Response({
        "metals": sorted(metals, key=lambda x: x["label"]),
        "linkers": sorted(linkers, key=lambda x: x["label"]),
        "guest_ions": guest_ions
    })

@api_view(["GET"])
def filter_mofs_dropdown(request):
    selected_metal = request.query_params.get("metal")
    selected_linker = request.query_params.get("linker")

    # CASE 1: User picks a metal -> Return only compatible linkers
    if selected_metal and not selected_linker:
        options = list(mof_index.METAL_TO_LINKERS.get(selected_metal, []))
        return JsonResponse({"results": [{"type": "linker", "value": val} for val in options]})

    # CASE 2: User picks a linker -> Return only compatible metals
    if selected_linker and not selected_metal:
        options = list(mof_index.LINKER_TO_METALS.get(selected_linker, []))
        return JsonResponse({"results": [{"type": "metal", "value": val} for val in options]})

    # CASE 3: Both selected -> Check if the combination exists in the registries
    if selected_metal and selected_linker:
        valid_linkers = mof_index.METAL_TO_LINKERS.get(selected_metal, set())
        if selected_linker in valid_linkers:
            return JsonResponse({"results": [{"status": "valid"}]})
        return JsonResponse({"results": [{"status": "invalid"}]}, status=404)

    return JsonResponse({"error": "Invalid request"}, status=400)
        
@api_view(["POST"])
def generate_mof_code(request):
    metal = request.data.get("metal")
    linker = request.data.get("linker")
    guest_ion = request.data.get("guest_ion")
    simple_mode = request.data.get("simple_mode", False)

    if not metal or not linker:
        return Response({"error": "Both a metal and a linker must be selected."}, status=400)

    mof_id = mof_index.find_mof(metal, linker)
    if mof_id is None:
        return Response(
            {"error": f"No mono-metal, mono-linker MOF found for metal '{metal}' and linker '{linker}'."},
            status=404,
        )

    metrics = mof_index.get_metrics(mof_id)
    if metrics is None or metrics["lcd"] is None or metrics["pld"] is None:
        return Response(
            {"error": f"MOF '{mof_id}' was found but its structural metrics are incomplete."},
            status=404,
        )

    target_lcd = metrics["lcd"]
    target_pld = metrics["pld"]

    # No print() calls here — Skulpt's stdout console stays clean.
    # draw_lattice's real signature is (metal, linker_smiles, guest_ion, simple_mode);
    # LCD/PLD are looked up client-side by MOFRenderer itself, not passed in.
    python_script = f"""
import mof_renderer

metal_ion = "{metal}"
linker_smiles = "{linker}"
guest_ion = "{guest_ion if guest_ion else 'None'}"
simple_mode = {simple_mode}

mof_renderer.draw_lattice(metal_ion, linker_smiles, guest_ion, simple_mode)
"""

    readout = _build_pore_readout(target_lcd, target_pld, guest_ion)

    return Response({"code": python_script.strip(), "readout": readout}, status=status.HTTP_200_OK)


def _build_pore_readout(lcd, pld, guest_ion):
    """
    Plain-data pore readout payload. No labels, definitions, or formatting
    here — MofReadoutPanel.tsx owns all presentation. This only computes
    the numeric values the panel needs.
    """
    readout = {
        "lcd": lcd,
        "pld": pld,
        "lcd_radius": lcd / 2,
        "pld_radius": pld / 2,
        "guest_ion": guest_ion or None,
        "guest_ion_known": None,       # True / False / None (no ion selected)
        "guest_ionic_radius": None,
        "guest_hydrated_radius": None,
    }

    if guest_ion:
        entry = ION_RADII.get(guest_ion)
        if entry:
            ionic_ang, hydrated_ang, _verified = entry
            readout["guest_ion_known"] = True
            readout["guest_ionic_radius"] = ionic_ang
            readout["guest_hydrated_radius"] = hydrated_ang
        else:
            readout["guest_ion_known"] = False

    return readout

@api_view(["GET"])
def get_mof_engine_file(request, filename):
    """
    Streams engine files securely to the Skulpt browser interpreter
    by checking requests against an explicit whitelist register.
    """
    whitelist = [
        "smiles_lexer.py", "smiles_parser.py", "layout_engine.py",
        "ring_utils.py", "ring_layout.py", "coordination_geometry.py", 
        "turtle_renderer.py",
        "mof_renderer.py",
    ]

    if filename == "mof_data.py":
        try:
            return HttpResponse(_mof_data_source_cached(), content_type="text/x-python")
        except Exception as e:
            return HttpResponse(f"# Error: {str(e)}", status=500, content_type="text/x-python")

    if filename not in whitelist:
        return HttpResponse("# Access Forbidden", status=403, content_type="text/x-python")

    paths_to_check = [
        Path(settings.BASE_DIR) / "api" / "mof_engine" / filename,
        Path(settings.BASE_DIR) / "api" / filename,
        Path(settings.BASE_DIR) / "assets" / filename,
        Path(settings.BASE_DIR).parent / "api" / filename
    ]

    filepath = None
    for p in paths_to_check:
        if p.is_file():
            filepath = p
            break

    if not filepath:
        print(f"\n[ENGINE 404 DIAGNOSTIC] Could not find {filename}!")
        print("Checked locations:")
        for p in paths_to_check:
            print(f"  -> {p.resolve()}")
        return HttpResponse(f"# Error: Engine file {filename} not found on server storage.", status=404, content_type="text/x-python")

    response = HttpResponse(open(filepath, 'rb').read(), content_type='text/x-python')
    return response