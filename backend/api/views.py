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
# Dynamic mof_data.py Structural Rebuilder
############################################
def _build_mof_data_source():
    """Read MOF_data.csv from disk and return generated `mof_data.py` source."""
    rows = []
    
    # 1. Print out diagnostic paths cleanly to your console
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
            
            # Substring matching to avoid encoding artifacts like 'Ã…'
            lcd_key = next((h for h in headers if "Largest Cavity" in h), None)
            pld_key = next((h for h in headers if "Pore Limiting" in h), None)
            id_key = next((h for h in headers if "Identifier" in h), None)
            metal_key = next((h for h in headers if "Metal Types" in h), None)

            if not (lcd_key and pld_key and id_key and metal_key):
                print(f"[MOF PARSER] ERROR: Missing vital header structural columns! (LCD: {lcd_key}, PLD: {pld_key}, ID: {id_key}, Metal: {metal_key})")
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


def _get_parsed_mof_db():
    """Retrieves the database dictionary by evaluating the generated source."""
    try:
        src = _get_mof_data_source_cached()
        if not src:
            return {}
        local_vars = {}
        exec(src, {}, local_vars)
        return local_vars.get("MOF_DB", {})
    except Exception as e:
        logger.error(f"Failed parsing cached mof data dict: {e}")
        return {}


def _get_mof_data_source_cached():
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
        src = _get_mof_data_source_cached()
        if not src:
            return {}
        local_vars = {}
        exec(src, {}, local_vars)
        return local_vars.get("MOF_DB", {})
    except Exception as e:
        logger.error(f"Failed parsing cached mof data dict: {e}")
        return {}

############################################
# Dynamic Search and Metadata Catalogs
############################################
@api_view(["GET"])
def get_mof_meta(request):
    try:
        mof_db = _get_parsed_mof_db()
    except Exception as e:
        logger.error(f"Error parsing MOF DB: {e}")
        mof_db = {}

    metals = set()
    linkers = set()
    
    for mof_id, (lcd, pld, metal_type) in mof_db.items():
        # Parse metals safely split by commas
        if metal_type:
            for m in [x.strip() for x in metal_type.split(",")]:
                if m:
                    metals.add(m)
        if mof_id and mof_id.strip():
            linkers.add(mof_id.strip())

    # Sort the outputs so they populate beautifully alphabetically
    return JsonResponse({
        "guest_ions": list(ION_RADII.keys()),
        "metals": sorted(list(metals)),
        "linkers": sorted(list(linkers)),
    }, status=200)


@api_view(["POST"])
def filter_mofs(request):
    # Support both JSON payload options (DRF request.data or standard raw json fallback)
    data = request.data if hasattr(request, 'data') else {}
    if not data and request.body:
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}

    selected_metal = data.get("metal")
    selected_linker = data.get("linker")
    
    try:
        mof_db = _get_parsed_mof_db()
    except Exception:
        mof_db = {}

    results = []
    for mof_id, (lcd, pld, metal_type) in mof_db.items():
        mof_metals = [x.strip() for x in metal_type.split(",")] if metal_type else []
        
        match_metal = not selected_metal or (selected_metal in mof_metals)
        match_linker = not selected_linker or (selected_linker == mof_id)
        
        if match_metal and match_linker:
            results.append({
                "mof_id": mof_id,
                "metal": metal_type,
                "lcd": lcd,
                "pld": pld
            })
            
    return JsonResponse({"results": results}, status=200)

############################################
# CSRF and Session Cookie Tokenizer Stubs
############################################
@ensure_csrf_cookie
def get_csrf_token(request):
    token = get_token(request)
    return JsonResponse({'csrfToken': token})


def check_cookie(request):
    token = request.COOKIES.get("gemini_token")
    return JsonResponse({"token_exists": bool(token)})


@csrf_exempt
def tokenize_key(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        body = json.loads(request.body)
        api_key = body.get("apiKey")
        if not api_key:
            return JsonResponse({"error": "API key is required"}, status=400)

        token = str(uuid.uuid4())
        cache.set(token, api_key.strip(), timeout=5400)
        
        response = JsonResponse({"message": "Token set."})
        response.set_cookie(
            key="gemini_token", value=token, max_age=5400,
            secure=not settings.DEBUG, httponly=True, samesite="Lax", path="/"
        )
        return response
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@api_view(["POST"])
@csrf_exempt
def clear_token(request):
    response = JsonResponse({"message": "Token cleared"})
    response.delete_cookie("gemini_token", path="/")
    return response


############################################
# Legacy/LLM Core Endpoint Handlers
############################################
@api_view(["GET"])
def list_models(request):
    return Response({"models": ["gemini-2.5-flash", "gemini-2.5-pro"]}, status=200)


@api_view(["POST"])
def test_api_key(request):
    token = request.COOKIES.get("gemini_token")
    api_key = cache.get(token) if token else None
    if not api_key:
        return Response({"valid": False, "error": "No API Key stored"}, status=401)
    return Response({"valid": True})


@api_view(["POST"])
def ask_gemini(request):
    return Response({"text": "LLM text processing response stub"})


@api_view(["POST"])
def prime_gemini(request):
    return Response({"status": "primed"})


@api_view(["POST"])
def ask_gemini_with_data(request):
    return Response({"text": "Data retrieval generation stub"})


############################################
# Gemini Execution Script Generation Engine
############################################
@api_view(["POST"])
@csrf_exempt
def generate_mof_code(request):
    data = request.data or {}
    metal = data.get("metal")
    linker = data.get("linker")
    guest_ion = data.get("guest_ion")
    simple_mode = data.get("simple_mode", False)

    if not metal or not linker:
        return Response({"error": "Both structural metal and organic linker choices are required."}, status=400)

    try:
        mof_db = _get_parsed_mof_db()
    except Exception as e:
        return Response({"error": f"Failed database: {str(e)}"}, status=500)

    if linker not in mof_db:
        return Response({"error": "Framework structure not found in lists."}, status=404)

    lcd, pld, dataset_metals = mof_db[linker]
    if metal not in [m.strip() for m in dataset_metals.split(",")]:
        return Response({"error": f"Selected metal element {metal} is not present for this framework."}, status=400)

    script_lines = [
        "import turtle",
        "from mof_renderer import MOFRenderer",
        "t = turtle.Turtle()",
        "t.speed(0)",
        "turtle.delay(0)",
        "t.hideturtle()",
        # FIX: Swap metal and linker, and explicitly pass guest_ion down if needed
        f"renderer = MOFRenderer(t, {metal!r}, {linker!r}, cx=0, cy=0, guest_ion={guest_ion!r})",
    ]

    if simple_mode:
        if guest_ion and guest_ion in ION_RADII:
            script_lines.append("renderer.draw_simple_with_guest()")  # Remove {guest_ion!r}
        else:
            script_lines.append("renderer.draw_simple_without_guest()")
    else:
        if guest_ion and guest_ion in ION_RADII:
            script_lines.append("renderer.draw_with_guest()")         # Remove {guest_ion!r}
        else:
            script_lines.append("renderer.draw_without_guest()")

    return Response({"code": "\n".join(script_lines)}, status=200)


@api_view(["GET"])
def get_mof_engine_file(request, filename):
    whitelist = [
        "mof_renderer.py", "smiles_parser.py", "smiles_lexer.py",
        "layout_engine.py", "ring_layout.py", "ring_utils.py",
        "coordination_geometry.py", "turtle_renderer.py",
    ]

    if filename == "mof_data.py":
        try:
            return HttpResponse(_get_mof_data_source_cached(), content_type="text/x-python")
        except Exception as e:
            return HttpResponse(f"# Error: {str(e)}", status=500, content_type="text/x-python")

    if filename not in whitelist:
        return HttpResponse("# Access Forbidden", status=403, content_type="text/x-python")

    # Strategy: Check inside backend/api/ first, then check backend/assets/
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
        # Print a clear diagnostic to your clean console showing exactly where it checked
        print(f"\n[ENGINE 404 DIAGNOSTIC] Could not find {filename}!")
        print("Checked locations:")
        for p in paths_to_check:
            print(f"  - {p.resolve()}")
        return HttpResponse(f"# Script {filename} missing", status=404, content_type="text/x-python")

    with filepath.open(encoding="utf-8") as f:
        return HttpResponse(f.read(), content_type="text/x-python")