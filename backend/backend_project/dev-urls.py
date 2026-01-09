# Import needed modules
from django.contrib import admin
from django.urls import path, include

# Define URL patters for app navigation
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]