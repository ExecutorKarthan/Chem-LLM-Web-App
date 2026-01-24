# Standard library imports
import time
import os
import uuid
import json

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


############################################
# CSRF Token endpoint
############################################
@ensure_csrf_cookie
def get_csrf_token(request):
    """Return CSRF token for frontend"""
    token = get_token(request)
    response = JsonResponse({'csrfToken': token})
    return response


############################################
# Puzzle loader
############################################
def get_puzzles(request):
    code_dir = settings.BASE_DIR / "assets" / "puzzles"
    static_files_root = settings.BASE_DIR / "assets" / "static"

    puzzles = []

    for filename in os.listdir(code_dir):
        if not filename.endswith(".txt"):
            continue

        puzzle_id = os.path.splitext(filename)[0]
        code_path = code_dir / filename
        code = code_path.read_text()

        image_filename = f"{puzzle_id}.png"
        image_file_path = os.path.join(static_files_root, image_filename)

        if not os.path.exists(image_file_path):
            continue

        puzzles.append({
            "id": puzzle_id,
            "title": f"Puzzle {puzzle_id.replace('puzzle', '')}",
            "code": code,
            "image_url": f"{settings.STATIC_URL}{image_filename}",
        })

    return JsonResponse(puzzles, safe=False)


############################################
# Cookie existence check
############################################
def check_cookie(request):
    token = request.COOKIES.get("gemini_token")
    return JsonResponse({"token_exists": bool(token)})


############################################
# Tokenize API key into cache + secure cookie
############################################
@ensure_csrf_cookie
def tokenize_key(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)
    try:
        body = json.loads(request.body)
        api_key = body.get("apiKey")

        if not api_key:
            return JsonResponse({"error": "API key is required"}, status=400)

        # Strip whitespace from API key
        api_key = api_key.strip()
        
        print(api_key)

        print(f"=== TOKENIZE DEBUG ===")
        print(f"Storing API key (length: {len(api_key)})")
        print(f"First 10 chars: {api_key[:10]}...")
        print(f"API key type: {type(api_key)}")
        print(f"=====================")

        token = str(uuid.uuid4())
        
        # Store in cache
        cache.set(token, api_key, timeout=5400)
        
        # VERIFY IT WAS STORED
        retrieved = cache.get(token)
        print(f"=== VERIFICATION ===")
        print(f"Retrieved after storage: {retrieved is not None}")
        print(f"Keys match: {retrieved == api_key if retrieved else 'N/A'}")
        print(f"====================")

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
        return response

    except Exception as e:
        print(f"ERROR in tokenize_key: {e}")
        return JsonResponse(
            {"error": "Server error", "details": str(e)},
            status=500
        )

############################################
# List available models (DEBUG)
############################################
@api_view(["GET"])
def list_models(request):
    """Debug endpoint to list available Gemini models"""
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
        return Response({"models": model_names})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


############################################
# Test API key (DEBUG)
############################################
@api_view(["GET"])
def test_api_key(request):
    """Debug endpoint to test if the stored API key works"""
    token = request.COOKIES.get("gemini_token")
    if not token:
        return Response({"error": "No token"}, status=401)
    
    api_key = cache.get(token)
    if not api_key:
        return Response({"error": "Invalid token"}, status=403)
    
    try:
        # Test with the simplest possible request
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello"
        )
        return Response({
            "success": True,
            "api_key_works": True,
            "response": response.text
        })
    except Exception as e:
        return Response({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }, status=400)


############################################
# Gemini query endpoint
############################################
@api_view(["POST"])
def ask_gemini(request, max_retries=2, delay=2):
    model_names = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ]

    # Get token from cookie
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

    # Debug the API key
    print(f"=== API Key Debug ===")
    print(f"API key retrieved: {api_key is not None}")
    print(f"API key length: {len(api_key) if api_key else 0}")
    print(f"API key starts with: {api_key[:10] if api_key else 'N/A'}...")
    print(f"API key type: {type(api_key)}")
    print(f"====================")

    prompt = request.data.get("prompt")
    if not prompt:
        return Response(
            {"error": "Prompt is missing in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    client = genai.Client(api_key=api_key)

    for model_name in model_names:
        for attempt in range(max_retries):
            try:
                print(f"Trying model: {model_name} (Attempt {attempt + 1})")

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                return Response(
                    {"response": response.text},
                    status=status.HTTP_200_OK,
                )

            except ClientError as e:
                error_message = str(e)
                print(f"=== ClientError Debug ===")
                print(f"Error type: {type(e)}")
                print(f"Error message: {error_message}")
                if hasattr(e, 'status_code'):
                    print(f"Status code: {e.status_code}")
                if hasattr(e, 'message'):
                    print(f"Message attr: {e.message}")
                print(f"========================")
                
                # Invalid API key - no point trying other models
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    return Response(
                        {"error": "Invalid or unauthorized API key provided."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                
                # Quota exceeded - try next model
                if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    print(f"{model_name} quota exceeded, trying next model...")
                    break  # Break retry loop, move to next model
                
                # Other client errors - show full details
                print(f"Returning client error for {model_name}")
                return Response(
                    {"error": f"Client error with {model_name}: {error_message}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            except ServerError as e:
                if "UNAVAILABLE" in str(e):
                    print(f"{model_name} unavailable, retrying...")
                    time.sleep(delay * (2 ** attempt))
                    continue

                return Response(
                    {"error": f"Server error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            except Exception as e:
                print(f"=== Unexpected Error ===")
                print(f"Error type: {type(e)}")
                print(f"Error: {e}")
                print(f"========================")
                return Response(
                    {"error": f"Unexpected error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    return Response(
        {"error": "All Gemini models are currently unavailable or quota exceeded."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


############################################
# Clear token + cookie
############################################
@api_view(["POST"])
def clear_token(request):
    token = request.COOKIES.get("gemini_token")

    if token:
        cache.delete(token)

    response = JsonResponse({"message": "Token cleared."})
    response.delete_cookie("gemini_token", samesite="Lax")

    return response