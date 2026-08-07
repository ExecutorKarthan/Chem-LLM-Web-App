# Standard library imports
import time
import os
import re
import sys
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

current_dir = Path(__file__).resolve().parent
ion_registry_dir = current_dir.parent / "assets"
sys.path.append(str(ion_registry_dir))
from ion_registry import get_ion_metadata

# Set up logger
logger = logging.getLogger(__name__)

# ── Gemini auth pattern used throughout this file ──────────────────────────
# The frontend never holds the user's raw Gemini API key after the initial
# submit. `tokenize_key` exchanges it for a random UUID, stores the real key
# server-side in Django's cache keyed by that UUID, and sends the UUID back
# as an httponly `gemini_token` cookie. Every subsequent Gemini-calling view
# below repeats the same three steps: read `gemini_token` from the cookie,
# look up the real key in `cache`, then call the Gemini SDK with it. This
# keeps the actual API key out of client-side JS and out of every request
# body after the first one.
#
# ── Model fallback pattern ──────────────────────────────────────────────────
# `ask_gemini`, `prime_gemini`, and `ask_gemini_with_data` all delegate to
# `_call_gemini_with_fallback` (below), which tries the shared
# `GEMINI_MODEL_NAMES` list in order, skipping any model already known-dead
# for this key (see dead-model cache section), retrying the same model a
# couple times on a transient "UNAVAILABLE" server error, and falling
# through to the next model on quota exhaustion, a permanent per-key
# rejection, or a network error. This trades a bit of latency in the worst
# case for not surfacing a hard failure to the user just because the
# current default model is temporarily over quota or no longer available
# to this particular key.

# Locate assets folder safely relative to backend directory structure
MOF_DATA_CSV_PATH = Path(settings.BASE_DIR) / "assets" / "MOF_data.csv"

# In-memory engine cache for generated module sources
_mof_data_cache = {"mtime": None, "source": None}

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
    """Debug endpoint: reports whether a gemini_token cookie is present
    on the request and whether that token still resolves to a cached
    API key, without exposing the key itself in the response."""
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
    """
    Exchanges a raw Gemini API key (sent once, in the POST body) for an
    opaque token: generates a UUID, stores {uuid: api_key} in Django's
    cache for 90 minutes, and sets that UUID as an httponly cookie. See
    the module-level note above on why this indirection exists. Also
    round-trips a cache write/read before storing the real key, so a
    misconfigured cache backend fails loudly here instead of silently
    later when some other view tries to look the token up.
    """
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
            secure=True,
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
# Dead-model cache
#
# Some rejections mean a model will NEVER work for this key again, no
# matter how many times we retry: the key belongs to a paid-tier-only
# model, or the model has been sunset for this account ("no longer
# available to new users"). We remember those permanently (well, for
# a long TTL) per-token so we stop wasting a request on them. This is
# different from quota exhaustion (RESOURCE_EXHAUSTED), which is
# transient and should NOT be cached -- the model will work again
# later today or tomorrow.
############################################
DEAD_MODEL_CACHE_PREFIX = "gemini_dead_model:"
DEAD_MODEL_CACHE_TIMEOUT = 60 * 60 * 24 * 7  # 1 week -- re-checked periodically in
                                               # case billing changes or Google
                                               # re-adds a model to the free tier


def _dead_model_cache_key(token, model_name):
    return f"{DEAD_MODEL_CACHE_PREFIX}{token}:{model_name}"


def _mark_model_dead(token, model_name, reason):
    """Remember that this model is permanently unusable for this key."""
    cache.set(_dead_model_cache_key(token, model_name), reason, timeout=DEAD_MODEL_CACHE_TIMEOUT)


def _dead_model_reason(token, model_name):
    """Returns the cached reason string if this model is known-dead for this key, else None."""
    return cache.get(_dead_model_cache_key(token, model_name))


def _looks_like_deprecated_for_key(error_message: str) -> bool:
    """
    Model has been sunset for this specific key/account, independent of
    billing status. Seen in practice as a 404 NOT_FOUND with wording like
    'no longer available to new users'.
    """
    signals = ["no longer available", "NOT_FOUND"]
    lowered = error_message.lower()
    return any(s.lower() in lowered for s in signals)


def _looks_like_paid_only_rejection(error_message: str) -> bool:
    """
    Model exists but requires a paid/billing-enabled account. Google doesn't
    give one single clean error code for this, so we match on wording and
    status codes that have shown up in practice.
    """
    signals = [
        "not available on the free tier",
        "requires a billing account",
        "billing account is required",
        "FAILED_PRECONDITION",
        "PERMISSION_DENIED",
    ]
    lowered = error_message.lower()
    return any(s.lower() in lowered for s in signals)


############################################
# Shared Gemini model-fallback caller
#
# Consolidates the try/retry/fallback loop previously duplicated across
# ask_gemini, prime_gemini, and ask_gemini_with_data. Each of those views
# now just builds its own prompt and hands it to this function.
############################################
GEMINI_MODEL_NAMES = [
    "gemini-2.5-flash-lite",  # stable, highest free-tier RPD -- try first
    "gemini-2.5-flash",       # stable, fast, generous quota
    "gemini-2.5-pro",         # stable, most capable, tighter free-tier RPM
    "gemini-3-flash-preview", # preview -- unreliable, last resort
    "gemini-3.1-flash-lite",  # preview -- unreliable, last resort
]


def _call_gemini_with_fallback(client, token, prompt, log_prefix, max_retries=2, delay=2):
    """
    Tries each model in GEMINI_MODEL_NAMES in order against `prompt`,
    skipping any model already known-dead for this token, retrying the
    same model up to `max_retries` times with exponential backoff only on
    a transient "UNAVAILABLE" server error, and falling through to the
    next model on quota exhaustion, a permanent per-key rejection
    (paid-only or deprecated-for-this-key -- these get cached as dead so
    future calls skip them instantly), or a network-level error.

    Returns a dict with EXACTLY ONE of:
      - {"text": str, "model_used": str, "warnings": list[str]}   on success
      - {"error_response": Response}                              on failure

    `log_prefix` (e.g. "ASK_GEMINI") is used to tag log lines so they can
    still be told apart per-endpoint even though the loop logic is shared.
    The caller is responsible for returning `error_response` directly and
    for building its own success Response from `text`/`model_used`/
    `warnings` (since each endpoint's success payload shape differs
    slightly, e.g. prime_gemini prefixes a confirmation message).
    """
    warnings = []

    for model_name in GEMINI_MODEL_NAMES:
        dead_reason = _dead_model_reason(token, model_name)
        if dead_reason:
            msg = f"Skipping {model_name} (previously unavailable: {dead_reason}), trying next model."
            logger.info(f"[{log_prefix}] {msg}")
            warnings.append(msg)
            continue

        for attempt in range(max_retries):
            try:
                logger.info(f"[{log_prefix}] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(model=model_name, contents=prompt)
                response_text = response.text if response.text is not None else ""
                logger.info(f"[{log_prefix}] SUCCESS with {model_name}. Response length: {len(response_text)}")
                logger.info("=" * 80)
                return {"text": response_text, "model_used": model_name, "warnings": warnings}

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[{log_prefix}] ClientError with {model_name}: {error_message}")

                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    logger.error(f"[{log_prefix}] FAILURE: Invalid API key")
                    logger.info("=" * 80)
                    return {"error_response": Response(
                        {"error": "Invalid or unauthorized API key provided."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )}

                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    msg = f"{model_name} hit its quota limit, trying next model."
                    logger.warning(f"[{log_prefix}] {msg}")
                    warnings.append(msg)
                    break  # transient -- do NOT blacklist, just move on for now

                if _looks_like_deprecated_for_key(error_message):
                    msg = f"{model_name} is no longer available for this API key, trying next model."
                    logger.warning(f"[{log_prefix}] {msg}")
                    _mark_model_dead(token, model_name, "deprecated for this key")
                    warnings.append(msg)
                    break

                if _looks_like_paid_only_rejection(error_message):
                    msg = f"{model_name} requires a paid account, trying next model."
                    logger.warning(f"[{log_prefix}] {msg}")
                    _mark_model_dead(token, model_name, "requires paid tier")
                    warnings.append(msg)
                    break

                logger.info("=" * 80)
                return {"error_response": Response(
                    {"error": f"Client error with {model_name}: {error_message}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )}

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[{log_prefix}] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue
                logger.error(f"[{log_prefix}] ServerError: {e}", exc_info=True)
                logger.info("=" * 80)
                return {"error_response": Response(
                    {"error": f"Server error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )}

            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                msg = f"Network error reaching {model_name}, trying next model."
                logger.warning(f"[{log_prefix}] {msg}: {e}")
                warnings.append(msg)
                break  # move to next model
            except Exception as e:
                logger.error(f"[{log_prefix}] Unexpected error: {e}", exc_info=True)
                logger.info("=" * 80)
                return {"error_response": Response(
                    {"error": f"Unexpected error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )}

    logger.error(f"[{log_prefix}] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return {"error_response": Response(
        {
            "error": "All Gemini models are currently unavailable or quota exceeded.",
            "warnings": warnings,
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )}


############################################
# Gemini query endpoint
############################################
@csrf_exempt
@api_view(["POST"])
def ask_gemini(request, max_retries=2, delay=2):
    """
    Sends `prompt` to Gemini using the API key resolved from the
    caller's gemini_token cookie (see module-level auth note), via the
    shared `_call_gemini_with_fallback` model-fallback loop (see that
    function's docstring for the retry/fallback rules).

    On success, the response includes a `warnings` list describing any
    models that were skipped or failed along the way, so the caller
    can surface that to the user instead of it only living in logs.
    """
    logger.info("=" * 80)
    logger.info("[ASK_GEMINI] ========== NEW REQUEST ==========")

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

    result = _call_gemini_with_fallback(client, token, prompt, "ASK_GEMINI", max_retries=max_retries, delay=delay)
    if "error_response" in result:
        return result["error_response"]

    return Response(
        {"response": result["text"], "model_used": result["model_used"], "warnings": result["warnings"]},
        status=status.HTTP_200_OK,
    )


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
    Sends the MOF CSV data to Gemini as a standalone priming call, via
    the shared `_call_gemini_with_fallback` model-fallback loop. Returns
    Gemini's acknowledgment response, prefaced with a success message.
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

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[PRIME_GEMINI] Failed to create Gemini client: {e}", exc_info=True)
        return Response({"error": f"Failed to create Gemini client: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    result = _call_gemini_with_fallback(client, token, priming_prompt, "PRIME_GEMINI", max_retries=max_retries, delay=delay)
    if "error_response" in result:
        return result["error_response"]

    return Response(
        {
            "response": "✅ MOF data was successfully submitted to Gemini.\n\n" + result["text"],
            "model_used": result["model_used"],
            "warnings": result["warnings"],
        },
        status=status.HTTP_200_OK,
    )


############################################
# Gemini query endpoint WITH CSV prepended
############################################
@csrf_exempt
@api_view(["POST"])
def ask_gemini_with_data(request, max_retries=2, delay=2):
    """
    Same as ask_gemini but prepends the full MOF CSV to every prompt
    so Gemini has the reference data available for every question, via
    the shared `_call_gemini_with_fallback` model-fallback loop.
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

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] Failed to create Gemini client: {e}", exc_info=True)
        return Response({"error": f"Failed to create Gemini client: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    result = _call_gemini_with_fallback(client, token, full_prompt, "ASK_GEMINI_WITH_DATA", max_retries=max_retries, delay=delay)
    if "error_response" in result:
        return result["error_response"]

    return Response(
        {"response": result["text"], "model_used": result["model_used"], "warnings": result["warnings"]},
        status=status.HTTP_200_OK,
    )


############################################
# Clear token + cookie
############################################
@csrf_exempt
@api_view(["POST"])
def clear_token(request):
    """Logs the user out of Gemini: deletes the cached API key (if the
    gemini_token cookie is present and still resolves to one) and
    clears the cookie itself from the response."""
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
    """
    Returns the generated `mof_data.py` source, regenerating it from
    MOF_data.csv only when the CSV's mtime has changed since the last
    call. This avoids re-parsing and re-serializing the whole CSV on
    every request to `get_mof_engine_file` for "mof_data.py" (which the
    Skulpt frontend fetches on every MOF render), while still picking
    up edits to the CSV without needing a server restart.
    """
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

    # CASE 2: User picks a linker -> Return compatible metals AND the common name
    if selected_linker and not selected_metal:
        options = list(mof_index.LINKER_TO_METALS.get(selected_linker, []))
        # Retrieve the common name if available
        common_name = mof_index.LINKER_TO_NAME.get(selected_linker, "")
        
        return JsonResponse({
            "results": [{"type": "metal", "value": val} for val in options],
            "common_name": common_name
        })

    # CASE 3: Both selected -> Check validity AND provide common name for display
    if selected_metal and selected_linker:
        valid_linkers = mof_index.METAL_TO_LINKERS.get(selected_metal, set())
        if selected_linker in valid_linkers:
            common_name = mof_index.LINKER_TO_NAME.get(selected_linker, "")
            return JsonResponse({
                "results": [{"status": "valid"}],
                "common_name": common_name
            })
        return JsonResponse({"results": [{"status": "invalid"}]}, status=404)

    return JsonResponse({"error": "Invalid request"}, status=400)
        
@api_view(["POST"])
def generate_mof_code(request):
    """
    Resolves the requested metal+linker combination to a known MOF
    entry, then returns a small Python source string (not run here) that
    the frontend hands to Skulpt to execute in-browser via
    `mof_renderer.draw_lattice(...)`. The values below are inlined as
    literals directly into that string, since Skulpt runs it as
    standalone script text with no way to receive Python objects from
    the Django side. Also returns the pore/guest-ion readout data
    alongside it so the frontend doesn't need a second round trip.
    """
    metal = request.data.get("metal")
    linker = request.data.get("linker")
    guest_ion = request.data.get("guest_ion")
    guest_ion_metadata = get_ion_metadata(guest_ion)
    simple_mode = request.data.get("simple_mode", False)

    if not metal or not linker:
        return Response({"error": "Both a metal and a linker must be selected."}, status=400)

    # 1. Resolve the ID via your existing index logic
    mof_id = mof_index.find_mof(metal, linker)
    if mof_id is None:
        return Response({"error": f"..."}, status=404)

    metrics = mof_index.get_metrics(mof_id)
    if metrics is None or metrics["lcd"] is None or metrics["pld"] is None:
        return Response({"error": f"..."}, status=404)

    # 2. Inject the mof_id into the Python script string
    # We pass it as a named argument to draw_lattice
    python_script = f"""
import mof_renderer

metal_ion = "{metal}"
linker_smiles = "{linker}"
guest_ion = "{guest_ion if guest_ion else 'None'}"
guest_ion_metadata = {guest_ion_metadata if guest_ion_metadata else 'None'}
simple_mode = {simple_mode}
mof_id = "{mof_id}"  

mof_renderer.draw_lattice(
    metal=metal_ion, 
    linker_smiles=linker_smiles, 
    mof_id=mof_id,      
    guest_ion=guest_ion, 
    guest_ion_metadata=guest_ion_metadata,
    simple_mode=simple_mode
)
"""
    
    print("--- GENERATED PYTHON CODE START ---")
    print(python_script)
    print("--- GENERATED PYTHON CODE END ---")

    readout = _build_pore_readout(metrics["lcd"], metrics["pld"], guest_ion)

    return Response({"code": python_script.strip(), "readout": readout}, status=status.HTTP_200_OK)

def _build_pore_readout(lcd, pld, guest_ion):
    """
    Constructs the readout payload including ion verification metadata.
    """
    # Fetch ion data: (ionic_r, hydrated_r, source)
    ion_metadata = get_ion_metadata(guest_ion) if guest_ion else {}
    
    # Extract values or None
    guest_ionic = ion_metadata[0]
    guest_hydrated = ion_metadata[1]
    source = ion_metadata[2]

    return {
        "lcd": lcd,
        "pld": pld,
        "lcd_radius": lcd / 2,
        "pld_radius": pld / 2,
        "guest_ion": guest_ion,
        "guest_ion_known": guest_ion is not None and guest_ionic is not None,
        "guest_ionic_radius": guest_ionic,
        "guest_hydrated_radius": guest_hydrated,
        "guest_ion_source": source  
    }

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