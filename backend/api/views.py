# Standard library imports
import time
import os
import uuid
import json

# Django / DRF imports
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Google Gemini (NEW SDK)
from google import genai
from google.genai.errors import ClientError, ServerError


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
@csrf_exempt
def tokenize_key(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        body = json.loads(request.body)
        api_key = body.get("apiKey")

        if not api_key:
            return JsonResponse({"error": "API key is required"}, status=400)

        token = str(uuid.uuid4())
        cache.set(token, api_key, timeout=5400)

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
        return JsonResponse(
            {"error": "Server error", "details": str(e)},
            status=500
        )


############################################
# Gemini query endpoint
############################################
@api_view(["POST"])
def ask_gemini(request, max_retries=2, delay=2):
    model_names = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
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
                if "API_KEY_INVALID" in error_message or "API key not valid" in error_message:
                    return Response(
                        {"error": "Invalid or unauthorized API key provided."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                return Response(
                    {"error": f"Client error: {error_message}"},
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
                return Response(
                    {"error": f"Unexpected error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    return Response(
        {"error": "All Gemini models are currently unavailable."},
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
