#!/bin/bash
# =============================================================================
# container_start.sh
# Runs INSIDE the Apptainer container on every start.
# Source files are bind-mounted from the host at /app/source.
# =============================================================================

set -e  # Exit immediately on any error

LOG="/app/logs/startup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[${TIMESTAMP}] $1" | tee -a "$LOG"
}

log "========================================"
log "Container startup beginning"
log "========================================"

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
SOURCE_DIR="/app/source/Chem-LLM-Web-App"   # bind-mounted from host's 'current' symlink
BACKEND_DIR="$SOURCE_DIR/backend"
FRONTEND_DIR="$SOURCE_DIR/frontend"
VENV_PYTHON="/opt/venv/bin/python"
VENV_PIP="/opt/venv/bin/pip"
GUNICORN="/opt/venv/bin/gunicorn"

# ─────────────────────────────────────────────────────────────────────────────
# Validate source is mounted
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -d "$SOURCE_DIR" ]; then
    log "ERROR: Source directory not found at $SOURCE_DIR"
    log "Make sure the bind mount is configured correctly in deploy.sh"
    exit 1
fi

log "Source directory confirmed: $SOURCE_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Install / update Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 1: Installing Python dependencies ---"
cd "$BACKEND_DIR"

$VENV_PIP install --upgrade pip setuptools wheel >> "$LOG" 2>&1
$VENV_PIP install -r requirements.txt >> "$LOG" 2>&1

log "Python version: $($VENV_PYTHON --version)"
log "Gunicorn version: $($GUNICORN --version)"
log "Python dependencies installed"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Validate .env file exists
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 2: Checking .env file ---"
ENV_FILE="$BACKEND_DIR/backend_project/.env"

if [ ! -f "$ENV_FILE" ]; then
    log "ERROR: .env file not found at $ENV_FILE"
    log "Run deploy.sh first to generate it, or create it manually."
    log "Required contents:"
    log "  DJANGO_SECRET_KEY=<generated key>"
    log "  DJANGO_DEBUG=False"
    log "  PRODUCTION_DOMAIN=YOUR_APP_DOMAIN_HERE.engr.wustl.edu"
    exit 1
fi

log ".env file found"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Build React frontend
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 3: Building React frontend ---"
cd "$FRONTEND_DIR"

log "Node version: $(node --version)"
log "npm version: $(npm --version)"

npm install >> "$LOG" 2>&1
log "npm install complete"

npm run build >> "$LOG" 2>&1
log "React build complete"

# Confirm WASM was copied by the vite plugin
if [ -f "$FRONTEND_DIR/dist/RDKit_minimal.wasm" ]; then
    log "RDKit_minimal.wasm confirmed in dist/"
else
    log "WARNING: RDKit_minimal.wasm not found in dist/ — molecule viewer may not work"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 4. Django setup
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 4: Django setup ---"
cd "$BACKEND_DIR"

$VENV_PYTHON manage.py migrate --noinput >> "$LOG" 2>&1
log "Database migrations complete"

$VENV_PYTHON manage.py collectstatic --noinput >> "$LOG" 2>&1
log "Static files collected"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Start Gunicorn
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 5: Starting Gunicorn ---"
log "Binding to 0.0.0.0:8000"
log "========================================"
log "Startup complete — handing off to Gunicorn"
log "========================================"

exec $GUNICORN backend_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile "$LOG" \
    --error-logfile "$LOG" \
    --log-level info
