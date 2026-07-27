# Import needed modules
import os
from django.core.wsgi import get_wsgi_application

#Sets environmental variables for WSGI entry point
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')

#Starts WSGI app — this is the entry point Gunicorn actually loads in
# deployment (matches settings.WSGI_APPLICATION = "backend_project.wsgi.
# application"), as opposed to asgi.py which appears to be unused
# boilerplate.
application = get_wsgi_application()
