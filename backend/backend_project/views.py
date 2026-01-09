# backend_project/views.py
from django.shortcuts import render
from django.http import Http404
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def frontend(request):
    """
    Serve the React SPA index.html for all non-API routes.
    """
    # Calculate React build path dynamically
    react_build_dir = Path(settings.BASE_DIR.parent) / "frontend" / "dist"
    index_path = react_build_dir / "index.html"
    
    # Debug logging
    logger.info(f"Looking for React build at: {react_build_dir}")
    logger.info(f"Index.html exists: {index_path.exists()}")
    
    if not index_path.exists():
        logger.error(f"React build not found at: {index_path}")
        logger.error(f"BASE_DIR: {settings.BASE_DIR}")
        logger.error(f"Expected parent: {settings.BASE_DIR.parent}")
        raise Http404(f"React build not found. Expected at: {index_path}")
    
    # Use Django's render to serve the template
    # This is better than FileResponse as it integrates with Django's template system
    try:
        return render(request, "index.html")
    except Exception as e:
        logger.error(f"Error rendering index.html: {e}")
        raise Http404(f"Error serving React app: {e}")