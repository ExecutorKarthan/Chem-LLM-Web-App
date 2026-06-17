# Standard library imports
import time
import os
import uuid
import json
import logging
import csv

# Django / DRF imports
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.cache import cache
from django.middleware.csrf import get_token

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Google Gemini (NEW SDK)
from google import genai
from google.genai.errors import ClientError, ServerError

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
    
    # Log all cookies
    all_cookies = request.COOKIES
    logger.info(f"[CHECK_COOKIE] All cookies present: {list(all_cookies.keys())}")
    
    token = request.COOKIES.get("gemini_token")
    logger.info(f"[CHECK_COOKIE] gemini_token exists: {bool(token)}")
    if token:
        logger.info(f"[CHECK_COOKIE] Token value: {token}")
        
        # Check if token exists in Redis
        cached_value = cache.get(token)
        logger.info(f"[CHECK_COOKIE] Token found in Redis: {cached_value is not None}")
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

        # Strip whitespace from API key
        api_key = api_key.strip()
        logger.info(f"[TOKENIZE] API key length: {len(api_key)}")
        logger.info(f"[TOKENIZE] API key preview: {api_key[:10]}...")
        logger.info(f"[TOKENIZE] API key type: {type(api_key)}")

        # Generate token
        token = str(uuid.uuid4())
        logger.info(f"[TOKENIZE] Generated token: {token}")
        
        # Test Redis connection before storing
        try:
            cache.set("test_connection", "test_value", timeout=10)
            test_retrieve = cache.get("test_connection")
            logger.info(f"[TOKENIZE] Redis connection test: {test_retrieve == 'test_value'}")
            cache.delete("test_connection")
        except Exception as redis_err:
            logger.error(f"[TOKENIZE] Redis connection test FAILED: {redis_err}")
            return JsonResponse(
                {"error": "Redis connection failed", "details": str(redis_err)},
                status=500
            )
        
        # Store in cache
        logger.info(f"[TOKENIZE] Storing in Redis with key: {token}")
        cache.set(token, api_key, timeout=5400)
        logger.info("[TOKENIZE] Storage complete")
        
        # VERIFY IT WAS STORED
        retrieved = cache.get(token)
        logger.info(f"[TOKENIZE] Verification - Retrieved from Redis: {retrieved is not None}")
        if retrieved:
            logger.info(f"[TOKENIZE] Verification - Retrieved length: {len(retrieved)}")
            logger.info(f"[TOKENIZE] Verification - Retrieved preview: {retrieved[:10]}...")
            logger.info(f"[TOKENIZE] Verification - Keys match: {retrieved == api_key}")
        else:
            logger.error("[TOKENIZE] CRITICAL: Failed to retrieve from Redis after storage!")
            return JsonResponse(
                {"error": "Failed to store token in cache"},
                status=500
            )

        response = JsonResponse({"message": "Token set in secure cookie."})
        response.set_cookie(
            key="gemini_token",
            value=token,
            max_age=5400,
            secure=True,
            httponly=True,
            samesite="None",
            path="/",
        )
        logger.info("[TOKENIZE] Cookie set in response")
        logger.info("=" * 80)
        return response

    except Exception as e:
        logger.error(f"[TOKENIZE] ERROR: {e}", exc_info=True)
        return JsonResponse(
            {"error": "Server error", "details": str(e)},
            status=500
        )


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
    logger.info(f"[LIST_MODELS] Token from cookie: {token}")
    
    if not token:
        logger.error("[LIST_MODELS] No token in cookies")
        return Response({"error": "No token"}, status=401)
    
    api_key = cache.get(token)
    logger.info(f"[LIST_MODELS] API key retrieved from cache: {api_key is not None}")
    
    if not api_key:
        logger.error("[LIST_MODELS] Token not found in Redis")
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
    logger.info(f"[TEST_KEY] Token from cookie: {token}")
    
    if not token:
        logger.error("[TEST_KEY] No token in cookies")
        return Response({"error": "No token"}, status=401)
    
    api_key = cache.get(token)
    logger.info(f"[TEST_KEY] API key retrieved from cache: {api_key is not None}")
    if api_key:
        logger.info(f"[TEST_KEY] API key length: {len(api_key)}")
        logger.info(f"[TEST_KEY] API key preview: {api_key[:10]}...")
    
    if not api_key:
        logger.error("[TEST_KEY] Token not found in Redis")
        return Response({"error": "Invalid token"}, status=403)
    
    try:
        # Test with the simplest possible request
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello"
        )
        logger.info("[TEST_KEY] API key works! Response received")
        logger.info("=" * 80)
        return Response({
            "success": True,
            "api_key_works": True,
            "response": response.text
        })
    except Exception as e:
        logger.error(f"[TEST_KEY] Error: {e}", exc_info=True)
        logger.info("=" * 80)
        return Response({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }, status=400)


############################################
# Gemini query endpoint
############################################
@csrf_exempt
@api_view(["POST"])
def ask_gemini(request, max_retries=2, delay=2):
    logger.info("=" * 80)
    logger.info("[ASK_GEMINI] ========== NEW REQUEST ==========")
    logger.info(f"[ASK_GEMINI] Request method: {request.method}")
    logger.info(f"[ASK_GEMINI] Request path: {request.path}")
    
    # Log all cookies
    all_cookies = request.COOKIES
    logger.info(f"[ASK_GEMINI] All cookies: {list(all_cookies.keys())}")
    for key, value in all_cookies.items():
        if key == "csrftoken":
            logger.info(f"[ASK_GEMINI] Cookie '{key}': {value[:10]}...")
        else:
            logger.info(f"[ASK_GEMINI] Cookie '{key}': {value}")
    
    # Log all headers
    logger.info("[ASK_GEMINI] Request headers:")
    for header, value in request.headers.items():
        if 'token' in header.lower() or 'csrf' in header.lower():
            logger.info(f"[ASK_GEMINI]   {header}: {value[:20]}..." if len(value) > 20 else f"[ASK_GEMINI]   {header}: {value}")
    
    model_names = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ]

    # Get token from cookie
    token = request.COOKIES.get("gemini_token")
    logger.info(f"[ASK_GEMINI] Step 1: Extracting token from cookies")
    logger.info(f"[ASK_GEMINI] Token found in cookies: {token is not None}")
    
    if not token:
        logger.error("[ASK_GEMINI] FAILURE: No gemini_token cookie present")
        logger.info("=" * 80)
        return Response(
            {"error": "Missing gemini_token cookie."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    logger.info(f"[ASK_GEMINI] Token value: {token}")
    logger.info(f"[ASK_GEMINI] Token length: {len(token)}")

    # Try to get API key from cache
    logger.info(f"[ASK_GEMINI] Step 2: Retrieving API key from Redis using token")
    try:
        api_key = cache.get(token)
        logger.info(f"[ASK_GEMINI] API key retrieved from Redis: {api_key is not None}")
    except Exception as cache_error:
        logger.error(f"[ASK_GEMINI] Redis error: {cache_error}", exc_info=True)
        logger.info("=" * 80)
        return Response(
            {"error": f"Cache error: {str(cache_error)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    
    if not api_key:
        logger.error("[ASK_GEMINI] FAILURE: Token not found in Redis cache")
        logger.info("[ASK_GEMINI] Checking what's in Redis...")
        
        # Debug: Try to see what keys exist in Redis
        try:
            # Test if Redis is responsive
            cache.set("test_key", "test_value", timeout=10)
            test_result = cache.get("test_key")
            logger.info(f"[ASK_GEMINI] Redis is responsive: {test_result == 'test_value'}")
            cache.delete("test_key")
        except Exception as e:
            logger.error(f"[ASK_GEMINI] Redis is NOT responsive: {e}")
        
        logger.info("=" * 80)
        return Response(
            {"error": "Invalid or expired token."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Log API key details
    logger.info(f"[ASK_GEMINI] Step 3: API key validation")
    logger.info(f"[ASK_GEMINI] API key type: {type(api_key)}")
    logger.info(f"[ASK_GEMINI] API key length: {len(api_key)}")
    logger.info(f"[ASK_GEMINI] API key preview: {api_key[:10]}...")
    logger.info(f"[ASK_GEMINI] API key ends with: ...{api_key[-10:]}")

    # Get prompt
    prompt = request.data.get("prompt")
    logger.info(f"[ASK_GEMINI] Step 4: Extracting prompt")
    logger.info(f"[ASK_GEMINI] Prompt received: {prompt is not None}")
    
    if not prompt:
        logger.error("[ASK_GEMINI] FAILURE: No prompt in request")
        logger.info("=" * 80)
        return Response(
            {"error": "Prompt is missing in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    logger.info(f"[ASK_GEMINI] Prompt length: {len(prompt)}")
    logger.info(f"[ASK_GEMINI] Prompt preview: {prompt[:50]}...")

    # Create Gemini client
    logger.info(f"[ASK_GEMINI] Step 5: Creating Gemini client")
    try:
        client = genai.Client(api_key=api_key)
        logger.info("[ASK_GEMINI] Gemini client created successfully")
    except Exception as e:
        logger.error(f"[ASK_GEMINI] Failed to create Gemini client: {e}", exc_info=True)
        logger.info("=" * 80)
        return Response(
            {"error": f"Failed to create Gemini client: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Try models
    logger.info(f"[ASK_GEMINI] Step 6: Attempting to generate content with models")
    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                logger.info(f"[ASK_GEMINI] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                logger.info(f"[ASK_GEMINI] SUCCESS! Model {model_name} responded")

                # Handle None response.text (happens with thought_signature or other non-text parts)
                response_text = response.text if response.text is not None else ""
                logger.info(f"[ASK_GEMINI] Response length: {len(response_text)}")
                if response_text:
                    logger.info(f"[ASK_GEMINI] Response preview: {response_text[:100]}...")
                else:
                    logger.warning("[ASK_GEMINI] Response text is None, returning empty string")
                logger.info("=" * 80)

                return Response(
                    {"response": response_text},
                    status=status.HTTP_200_OK,
                )

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[ASK_GEMINI] ClientError with {model_name}: {error_message}")
                logger.error(f"[ASK_GEMINI] Error type: {type(e).__name__}")
                if hasattr(e, 'status_code'):
                    logger.error(f"[ASK_GEMINI] Status code: {e.status_code}")
                
                # Invalid API key - no point trying other models
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    logger.error("[ASK_GEMINI] FAILURE: Invalid API key")
                    logger.info("=" * 80)
                    return Response(
                        {"error": "Invalid or unauthorized API key provided."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                
                # Quota exceeded - try next model
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    logger.warning(f"[ASK_GEMINI] {model_name} quota exceeded, trying next model...")
                    break  # Break retry loop, move to next model
                
                # Other client errors - show full details
                logger.error(f"[ASK_GEMINI] Returning client error for {model_name}")
                logger.info("=" * 80)
                return Response(
                    {"error": f"Client error with {model_name}: {error_message}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[ASK_GEMINI] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue

                logger.error(f"[ASK_GEMINI] ServerError: {e}", exc_info=True)
                logger.info("=" * 80)
                return Response(
                    {"error": f"Server error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            except Exception as e:
                logger.error(f"[ASK_GEMINI] Unexpected error: {e}", exc_info=True)
                logger.error(f"[ASK_GEMINI] Error type: {type(e).__name__}")
                logger.info("=" * 80)
                return Response(
                    {"error": f"Unexpected error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    logger.error("[ASK_GEMINI] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return Response(
        {"error": "All Gemini models are currently unavailable or quota exceeded."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )

############################################
# Helper: load MOF CSV as formatted string
############################################
MOF_CSV_PATH = os.path.join(settings.BASE_DIR, "assets", "MOF_data.csv")

def load_mof_csv():
    """
    Reads the MOF CSV from disk and returns a formatted string
    suitable for inline injection into a Gemini prompt.
    Raises FileNotFoundError if the CSV is missing.
    Raises ValueError if the CSV is empty or malformed.
    """
    if not os.path.exists(MOF_CSV_PATH):
        logger.error(f"[MOF_CSV] File not found at: {MOF_CSV_PATH}")
        raise FileNotFoundError(
            f"MOF data file not found at {MOF_CSV_PATH}. "
            "Please ensure MOF_data.csv exists in backend/assets/."
        )

    rows = []
    with open(MOF_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("MOF CSV is empty or has no header row.")
        for row in reader:
            rows.append(row)

    if not rows:
        raise ValueError("MOF CSV has headers but contains no data rows.")

    logger.info(f"[MOF_CSV] Loaded {len(rows)} rows with columns: {headers}")

    # Format as a readable table for Gemini
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

    # --- Load the CSV ---
    try:
        csv_content = load_mof_csv()
    except FileNotFoundError as e:
        logger.error(f"[PRIME_GEMINI] CSV missing: {e}")
        return Response(
            {"error": str(e), "csv_missing": True},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValueError as e:
        logger.error(f"[PRIME_GEMINI] CSV invalid: {e}")
        return Response(
            {"error": str(e), "csv_missing": True},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # --- Authenticate ---
    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response(
            {"error": "Missing gemini_token cookie."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    api_key = cache.get(token)
    if not api_key:
        return Response(
            {"error": "Invalid or expired token."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # --- Build priming prompt ---
    priming_prompt = (
        "You are a chemistry assistant specialising in Metal-Organic Frameworks (MOFs) "
        "and Covalent Organic Frameworks (COFs). I am providing you with a reference "
        "dataset of MOF molecules in SMILES notation along with their framework "
        "properties. Please acknowledge you have received this data and briefly summarise "
        "what it contains so I know you are ready to answer questions about it.\n\n"
        f"{csv_content}"
    )

    logger.info(f"[PRIME_GEMINI] Priming prompt length: {len(priming_prompt)} chars")

    model_names = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ]

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[PRIME_GEMINI] Failed to create Gemini client: {e}", exc_info=True)
        return Response(
            {"error": f"Failed to create Gemini client: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                logger.info(f"[PRIME_GEMINI] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(
                    model=model_name,
                    contents=priming_prompt,
                )
                response_text = response.text if response.text is not None else ""
                logger.info(f"[PRIME_GEMINI] SUCCESS with {model_name}. Response length: {len(response_text)}")
                logger.info("=" * 80)

                success_prefix = "✅ MOF data was successfully submitted to Gemini.\n\n"
                return Response(
                    {"response": success_prefix + response_text},
                    status=status.HTTP_200_OK,
                )

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[PRIME_GEMINI] ClientError with {model_name}: {error_message}")
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    return Response(
                        {"error": "Invalid or unauthorized API key provided."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    logger.warning(f"[PRIME_GEMINI] {model_name} quota exceeded, trying next model...")
                    break
                return Response(
                    {"error": f"Client error with {model_name}: {error_message}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[PRIME_GEMINI] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue
                logger.error(f"[PRIME_GEMINI] ServerError: {e}", exc_info=True)
                return Response(
                    {"error": f"Server error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            except Exception as e:
                logger.error(f"[PRIME_GEMINI] Unexpected error: {e}", exc_info=True)
                return Response(
                    {"error": f"Unexpected error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    logger.error("[PRIME_GEMINI] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return Response(
        {"error": "All Gemini models are currently unavailable or quota exceeded."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


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

    # --- Load the CSV ---
    try:
        csv_content = load_mof_csv()
    except FileNotFoundError as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] CSV missing: {e}")
        return Response(
            {"error": str(e), "csv_missing": True},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValueError as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] CSV invalid: {e}")
        return Response(
            {"error": str(e), "csv_missing": True},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # --- Authenticate ---
    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response(
            {"error": "Missing gemini_token cookie."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    api_key = cache.get(token)
    if not api_key:
        return Response(
            {"error": "Invalid or expired token."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # --- Build prompt with prepended CSV ---
    prompt = request.data.get("prompt")
    if not prompt:
        return Response(
            {"error": "Prompt is missing in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    full_prompt = (
        "You are a chemistry assistant specialising in MOFs and COFs. "
        "Use the following MOF reference data to answer the user's question.\n\n"
        f"{csv_content}\n\n"
        f"USER QUESTION: {prompt}"
    )

    logger.info(f"[ASK_GEMINI_WITH_DATA] Full prompt length: {len(full_prompt)} chars")

    model_names = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ]

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[ASK_GEMINI_WITH_DATA] Failed to create Gemini client: {e}", exc_info=True)
        return Response(
            {"error": f"Failed to create Gemini client: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                logger.info(f"[ASK_GEMINI_WITH_DATA] Trying model: {model_name} (Attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )
                response_text = response.text if response.text is not None else ""
                logger.info(f"[ASK_GEMINI_WITH_DATA] SUCCESS with {model_name}. Response length: {len(response_text)}")
                logger.info("=" * 80)
                return Response(
                    {"response": response_text},
                    status=status.HTTP_200_OK,
                )

            except ClientError as e:
                error_message = str(e)
                logger.error(f"[ASK_GEMINI_WITH_DATA] ClientError with {model_name}: {error_message}")
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    return Response(
                        {"error": "Invalid or unauthorized API key provided."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    logger.warning(f"[ASK_GEMINI_WITH_DATA] {model_name} quota exceeded, trying next model...")
                    break
                return Response(
                    {"error": f"Client error with {model_name}: {error_message}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    logger.warning(f"[ASK_GEMINI_WITH_DATA] {model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue
                logger.error(f"[ASK_GEMINI_WITH_DATA] ServerError: {e}", exc_info=True)
                return Response(
                    {"error": f"Server error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            except Exception as e:
                logger.error(f"[ASK_GEMINI_WITH_DATA] Unexpected error: {e}", exc_info=True)
                return Response(
                    {"error": f"Unexpected error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    logger.error("[ASK_GEMINI_WITH_DATA] FAILURE: All models exhausted")
    logger.info("=" * 80)
    return Response(
        {"error": "All Gemini models are currently unavailable or quota exceeded."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )

############################################
# Clear token + cookie
############################################
@csrf_exempt
@api_view(["POST"])
def clear_token(request):
    logger.info("=" * 80)
    logger.info("[CLEAR_TOKEN] Request received")
    
    token = request.COOKIES.get("gemini_token")
    logger.info(f"[CLEAR_TOKEN] Token to clear: {token}")

    if token:
        cache.delete(token)
        logger.info("[CLEAR_TOKEN] Token deleted from Redis")
    else:
        logger.info("[CLEAR_TOKEN] No token to clear")

    response = JsonResponse({"message": "Token cleared."})
    response.delete_cookie("gemini_token", samesite="Lax")
    logger.info("[CLEAR_TOKEN] Cookie deleted from response")
    logger.info("=" * 80)
    
    return response