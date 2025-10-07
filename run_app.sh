#!/bin/bash
# ============================================================
# Build + Run Script for Django & React Apptainer Containers
# ============================================================
# Author: Xander
# Description:
#   - Builds both .sif images from .def files only if missing
#   - Verifies successful build
#   - Launches backend first, waits, then launches frontend
# ============================================================

set -e
set -o pipefail

BACKEND_DEF="llm-web-app-django-dev.def"
FRONTEND_DEF="llm-web-app-react-dev.def"
BACKEND_SIF="llm-web-app-django-dev.sif"
FRONTEND_SIF="llm-web-app-react-dev.sif"

############################################################
# 1. Verify Apptainer
############################################################
if ! command -v apptainer &>/dev/null; then
    echo "❌ Apptainer not found. Please install Apptainer before running this script."
    exit 1
fi

############################################################
# 2. Build Django Backend Container (if missing)
############################################################
echo "=== 🧱 Checking Django Backend Container ==="
if [ -f "$BACKEND_SIF" ]; then
    echo "✅ $BACKEND_SIF already exists — skipping build."
else
    echo "⚙️  Building Django backend container..."
    sudo apptainer build "$BACKEND_SIF" "$BACKEND_DEF"
    echo "✅ Backend container built successfully: $BACKEND_SIF"
fi

############################################################
# 3. Build React Frontend Container (if missing)
############################################################
echo "=== 🧱 Checking React Frontend Container ==="
if [ -f "$FRONTEND_SIF" ]; then
    echo "✅ $FRONTEND_SIF already exists — skipping build."
else
    echo "⚙️  Building React frontend container..."
    sudo apptainer build "$FRONTEND_SIF" "$FRONTEND_DEF"
    echo "✅ Frontend container built successfully: $FRONTEND_SIF"
fi

############################################################
# 4. Run Django Backend
############################################################
echo "=== 🚀 Starting Django Backend ==="
sudo apptainer run --net --network-args "portmap=8000:8000/tcp" "$BACKEND_SIF" &
BACKEND_PID=$!

############################################################
# 5. Wait for Backend Startup
############################################################
echo "⏳ Waiting for backend to initialize..."
sleep 15

# Optional quick port check (requires nc)
if command -v nc &>/dev/null; then
    if nc -z localhost 8000; then
        echo "✅ Django backend is responding on port 8000"
    else
        echo "⚠️ Backend may not be ready yet, continuing anyway..."
    fi
fi

############################################################
# 6. Run React Frontend
############################################################
echo "=== 🚀 Starting React Frontend ==="
sudo apptainer run --net --network-args "portmap=3000:3000/tcp" "$FRONTEND_SIF"

############################################################
# 7. Cleanup on exit
############################################################
trap "echo '🧹 Stopping backend...'; kill $BACKEND_PID 2>/dev/null || true" EXIT
wait $BACKEND_PID
