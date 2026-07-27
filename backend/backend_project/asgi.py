# Import needed modules
import os
from django.core.asgi import get_asgi_application

# Set environment variable for ASGI entry
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')

# Create ASGI application
#
# NOTE: settings.py sets WSGI_APPLICATION (not an ASGI equivalent), and
# this project's deployment (Gunicorn via Apptainer/pm2, per the
# project's deploy setup) runs the WSGI entry point in wsgi.py, not
# this one — this file is Django's standard project-template
# boilerplate and doesn't appear to be actively used unless something
# elsewhere (e.g. an ASGI server config) references it directly.
application = get_asgi_application()
