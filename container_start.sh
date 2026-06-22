#!/bin/bash
# =============================================================================
# container_start.sh
# Runs INSIDE the Apptainer container on every start.
# Python dependencies are already baked into the container image —
# only the React build and Django setup steps run here.
# =============================================================================

set -e

LOG="/app/logs/startup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG"
}

log "========================================"
log "Container startup beginning"
log "========================================"

# -------------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------------
SOURCE_DIR="/app/source/Chem-LLM-Web-App"   # bind-mounted from host 'current' symlink
BACKEND_DIR="$SOURCE_DIR/backend"
FRONTEND_DIR="$SOURCE_DIR/frontend"
VENV_PYTHON="/opt/venv/bin/python"
GUNICORN="/opt/venv/bin/gunicorn"

# -------------------------------------------------------------------------
# Validate source is mounted
# -------------------------------------------------------------------------
if [ ! -d "$SOURCE_DIR" ]; then
    log "ERROR: Source directory not found at $SOURCE_DIR"
    log "Make sure the bind mount is configured correctly in deploy.sh"
    exit 1
fi

log "Source directory confirmed: $SOURCE_DIR"

# -------------------------------------------------------------------------
# 1. Validate .env file exists
# -------------------------------------------------------------------------
log "--- Step 1: Checking .env file ---"
ENV_FILE="$BACKEND_DIR/backend_project/.env"

if [ ! -f "$ENV_FILE" ]; then
    log "ERROR: .env file not found at $ENV_FILE"
    log "This should have been symlinked by deploy.sh. Check deploy logs."
    exit 1
fi

log ".env file found"

# -------------------------------------------------------------------------
# 2. Build React frontend
# -------------------------------------------------------------------------
log "--- Step 2: Building React frontend ---"
cd "$FRONTEND_DIR"

log "Node version: $(node --version)"
log "npm version: $(npm --version)"

npm install >> "$LOG" 2>&1
log "npm install complete"

npm run build >> "$LOG" 2>&1
log "React build complete"

if [ -f "$FRONTEND_DIR/dist/RDKit_minimal.wasm" ]; then
    log "RDKit_minimal.wasm confirmed in dist/"
else
    log "WARNING: RDKit_minimal.wasm not found in dist/ -- molecule viewer may not work"
fi

# -------------------------------------------------------------------------
# 3. Django setup
# -------------------------------------------------------------------------
log "--- Step 3: Django setup ---"
cd "$BACKEND_DIR"

log "Python version: $($VENV_PYTHON --version)"
log "Django version: $($VENV_PYTHON -c 'import django; print(django.__version__)')"

$VENV_PYTHON manage.py migrate --noinput >> "$LOG" 2>&1
log "Database migrations complete"

$VENV_PYTHON manage.py collectstatic --noinput >> "$LOG" 2>&1
log "Static files collected"

# -------------------------------------------------------------------------
# 4. Start Gunicorn
# -------------------------------------------------------------------------
log "--- Step 4: Starting Gunicorn ---"
log "Binding to 0.0.0.0:8000"
log "========================================"
log "Startup complete -- handing off to Gunicorn"
log "========================================"

# Create file cache directory (must exist before Django starts)
mkdir -p /tmp/django_cache

exec $GUNICORN backend_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 300 \
    --preload \
    --access-logfile "$LOG" \
    --error-logfile "$LOG" \
    --log-level info