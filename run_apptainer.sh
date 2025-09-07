#!/usr/bin/env bash
set -e

# Point to system config instead of $HOME/etc
export APPTAINER_CONF=/etc/apptainer/apptainer.conf

# Build image (only if you want to rebuild each time)
apptainer build --force llm-web-app.sif llm-web-app.def

# Run both backend and frontend inside the container
apptainer exec \
  --bind "$(pwd):/opt/llm" \
  llm-web-app.sif \
  bash -c "
    cd /opt/llm &&
    npm install &&
    npm start
  "
