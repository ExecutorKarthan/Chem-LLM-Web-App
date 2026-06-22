# =============================================================================
# AUTO-UPDATE CRON JOB
# =============================================================================
#
# This cron job runs deploy.sh every 5 minutes.
# deploy.sh checks GitHub for changes — if none, it exits quickly.
# If changes are found, it pulls, rebuilds, and restarts via pm2.
#
# TO INSTALL:
#   1. Open crontab:   crontab -e
#   2. Add this line:
#
# */5 * * * * /var/www/chem-llm/cron_update.sh >> /var/www/chem-llm/logs/cron.log 2>&1
#
# =============================================================================

#!/bin/bash
# cron_update.sh
# Lightweight wrapper called by cron every 5 minutes.
# Checks for updates and triggers pm2 restart if needed.

APP_DIR="/var/www/chem-llm"
REPO_DIR="$APP_DIR/source/Chem-LLM-Web-App"
LOG="$APP_DIR/logs/cron.log"
DEPLOY_BRANCH="deploy"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Cron update check starting" >> "$LOG"

# If repo doesn't exist yet, pm2 / deploy.sh will handle it
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[$TIMESTAMP] Repo not yet cloned — skipping cron check" >> "$LOG"
    exit 0
fi

cd "$REPO_DIR"
git fetch origin "$DEPLOY_BRANCH" >> "$LOG" 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$DEPLOY_BRANCH")

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$TIMESTAMP] Update detected (${LOCAL:0:8} → ${REMOTE:0:8}) — restarting via pm2" >> "$LOG"
    # pm2 restart triggers deploy.sh which pulls and rebuilds
    pm2 restart chem-llm >> "$LOG" 2>&1
else
    echo "[$TIMESTAMP] No changes detected — nothing to do" >> "$LOG"
fi
