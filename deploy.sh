#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Chem-LLM-Web-App
#
# Just run this script — it finds everything else itself.
# All sibling files (chem-llm.def, container_start.sh, etc.) are copied
# into place automatically on first run.
#
# Usage:
#   bash deploy.sh
#
# =============================================================================

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Resolve script's own directory — sibling files live here
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# !! REPLACE YOUR_SUBDOMAIN once confirmed with WashU IT !!
# ─────────────────────────────────────────────────────────────────────────────
GITHUB_REPO="https://github.com/ExecutorKarthan/Chem-LLM-Web-App.git"
DEPLOY_BRANCH="ubuntu-deploy"

# APP_DIR -- toggle by commenting/uncommenting the appropriate line:
#   Zorin local testing  -->  uncomment the first line
#   Ubuntu server        -->  uncomment the second line
APP_DIR="$HOME/chem-llm-test"   # Zorin testing
#APP_DIR="/var/www/chem-llm"    # Ubuntu server
RELEASES_DIR="$APP_DIR/releases"
SHARED_DIR="$APP_DIR/shared"
LOG_DIR="$APP_DIR/logs"
SIF_FILE="$APP_DIR/chem-llm.sif"
DEF_FILE="$APP_DIR/chem-llm.def"
INSTALL_LOG="$APP_DIR/INSTALL_LOG.md"
PRODUCTION_DOMAIN="YOUR_SUBDOMAIN.chemistry.wustl.edu"   # !! REPLACE ME !!
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
NEW_RELEASE="$RELEASES_DIR/$TIMESTAMP"
ENV_FILE="$SHARED_DIR/.env"
PM2_CONFIG="$SHARED_DIR/ecosystem.config.js"

# ─────────────────────────────────────────────────────────────────────────────
# Create all required directories
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p "$APP_DIR" "$RELEASES_DIR" "$SHARED_DIR" "$LOG_DIR"

DEPLOY_LOG="$LOG_DIR/deploy.log"
TIMESTAMP_HUMAN=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP_HUMAN] $1" | tee -a "$DEPLOY_LOG"
}

log_install() {
    echo "$1" | tee -a "$INSTALL_LOG"
}

# ─────────────────────────────────────────────────────────────────────────────
# Self-bootstrap — copy sibling files into APP_DIR if not already there.
# This means you only need deploy.sh in front of you to get started.
# ─────────────────────────────────────────────────────────────────────────────
for f in chem-llm.def container_start.sh cron_update.sh; do
    if [ ! -f "$APP_DIR/$f" ]; then
        if [ -f "$SCRIPT_DIR/$f" ]; then
            cp "$SCRIPT_DIR/$f" "$APP_DIR/$f"
            chmod +x "$APP_DIR/$f" 2>/dev/null || true
        else
            echo "ERROR: $f not found next to deploy.sh ($SCRIPT_DIR/$f)"
            echo "Make sure all scripts branch files are in the same directory as deploy.sh"
            exit 1
        fi
    fi
done

if [ ! -f "$SHARED_DIR/ecosystem.config.js" ]; then
    if [ -f "$SCRIPT_DIR/ecosystem.config.js" ]; then
        cp "$SCRIPT_DIR/ecosystem.config.js" "$SHARED_DIR/ecosystem.config.js"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Initialize install log on first run
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -f "$INSTALL_LOG" ]; then
    log_install "# Chem-LLM-Web-App Installation Log"
    log_install ""
    log_install "Records every deploy run for troubleshooting."
    log_install ""
fi

log_install "## Deploy run: $TIMESTAMP_HUMAN"
log_install "- OS: $(uname -a)"
log_install "- Apptainer: $(apptainer --version 2>/dev/null || echo 'not found')"
log_install "- Git: $(git --version 2>/dev/null || echo 'not found')"
log_install ""

log "========================================"
log "Chem-LLM deploy.sh starting"
log "========================================"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check for updates and clone into a new timestamped release
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 1: Source code ---"
NEEDS_REBUILD=false
CURRENT_LINK="$APP_DIR/current"

place_container_start() {
    # The container's runscript looks for container_start.sh at
    # /app/source/container_start.sh, which bind-mounts to $NEW_RELEASE.
    # Since container_start.sh is not part of the git repo, we copy it
    # from APP_DIR (where the self-bootstrap placed it) into the release.
    cp "$APP_DIR/container_start.sh" "$1/container_start.sh"
    chmod +x "$1/container_start.sh"
    log "container_start.sh placed in release"
}

if [ ! -L "$CURRENT_LINK" ] || [ ! -d "$CURRENT_LINK" ]; then
    log "No current release found — cloning fresh"
    mkdir -p "$NEW_RELEASE"
    git clone --branch "$DEPLOY_BRANCH" "$GITHUB_REPO" "$NEW_RELEASE/Chem-LLM-Web-App" \
        >> "$DEPLOY_LOG" 2>&1
    log "Clone complete into $NEW_RELEASE"
    place_container_start "$NEW_RELEASE"
    log_install "- First clone from: $GITHUB_REPO (branch: $DEPLOY_BRANCH)"
    NEEDS_REBUILD=true
else
    CURRENT_REPO="$CURRENT_LINK/Chem-LLM-Web-App"
    cd "$CURRENT_REPO"
    git fetch origin "$DEPLOY_BRANCH" >> "$DEPLOY_LOG" 2>&1
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse "origin/$DEPLOY_BRANCH")

    if [ "$LOCAL" != "$REMOTE" ]; then
        log "Update found (${LOCAL:0:8} → ${REMOTE:0:8}) — cloning new release"
        mkdir -p "$NEW_RELEASE"
        git clone --branch "$DEPLOY_BRANCH" "$GITHUB_REPO" "$NEW_RELEASE/Chem-LLM-Web-App" \
            >> "$DEPLOY_LOG" 2>&1
        log "Clone complete into $NEW_RELEASE"
        place_container_start "$NEW_RELEASE"
        log_install "- Updated: ${LOCAL:0:8} → ${REMOTE:0:8}"
        NEEDS_REBUILD=true
    else
        log "Already up to date (${LOCAL:0:8}) — no new release needed"
        log_install "- No code changes (${LOCAL:0:8})"
        NEW_RELEASE=$(readlink -f "$CURRENT_LINK")
        log "Reusing existing release: $NEW_RELEASE"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Symlink .env into the release
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 2: Symlinking .env ---"
RELEASE_ENV="$NEW_RELEASE/Chem-LLM-Web-App/backend/backend_project/.env"

if [ ! -f "$ENV_FILE" ]; then
    log "No shared .env found — generating"
    SECRET_KEY=$(python3 -c "
import secrets, string
chars = string.ascii_letters + string.digits + '!@#\$%^&*(-_=+)'
print(''.join(secrets.choice(chars) for _ in range(50)))
")
    cat > "$ENV_FILE" << ENVEOF
# Auto-generated by deploy.sh on $TIMESTAMP_HUMAN
# Do not commit this file to git

DJANGO_SECRET_KEY=$SECRET_KEY
DJANGO_DEBUG=False

# !! REPLACE with your real subdomain once confirmed with WashU IT !!
PRODUCTION_DOMAIN=$PRODUCTION_DOMAIN
ENVEOF
    log ".env generated at $ENV_FILE"
    log_install "- .env generated (new secret key)"
else
    log "Shared .env exists — leaving untouched"
fi

ln -sfn "$ENV_FILE" "$RELEASE_ENV"
log ".env symlinked into release"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Build Apptainer container (only if source changed or no .sif exists)
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 3: Apptainer container ---"

if [ ! -f "$SIF_FILE" ] || [ "$NEEDS_REBUILD" = true ]; then
    [ -f "$SIF_FILE" ] && rm -f "$SIF_FILE"
    log "Building container (this takes a few minutes on first run)..."

    BUILD_START=$(date +%s)
    apptainer build "$SIF_FILE" "$DEF_FILE" >> "$DEPLOY_LOG" 2>&1
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))

    log "Container built in ${BUILD_TIME}s"
    log_install "- Container built: ${BUILD_TIME}s"
    log_install "- Python in container: $(apptainer exec "$SIF_FILE" python3 --version 2>/dev/null)"
    log_install "- Node in container:   $(apptainer exec "$SIF_FILE" node --version 2>/dev/null)"
    log_install "- npm in container:    $(apptainer exec "$SIF_FILE" npm --version 2>/dev/null)"
else
    log "Container up to date — skipping rebuild"
    log_install "- Container unchanged (no rebuild)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Switch symlink to new release
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 4: Switching symlink ---"
ln -sfn "$NEW_RELEASE" "$APP_DIR/current"
log "current → $NEW_RELEASE"

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Start the container
# ─────────────────────────────────────────────────────────────────────────────
log "--- Step 5: Starting container ---"
log "Source: $APP_DIR/current/Chem-LLM-Web-App"
log "Port:   8000 (Gunicorn inside) → 3001 (pm2) → 443 (nginx)"
log "========================================"
log "Handing off to Apptainer"
log "========================================"

exec apptainer run \
    --bind "$APP_DIR/current:/app/source" \
    --bind "$LOG_DIR:/app/logs" \
    --bind "$SHARED_DIR:/app/shared" \
    --writable-tmpfs \
    "$SIF_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Keep only last 5 releases (runs after container exits)
# ─────────────────────────────────────────────────────────────────────────────
ls -1dt "$RELEASES_DIR"/* 2>/dev/null | tail -n +6 | xargs -r rm -rf
log "Old releases pruned (keeping last 5)"