#!/bin/bash
# start-app.sh

echo "Starting Django backend on :8000..."
cd /opt/app/backend

# Start Django backend in the background
python3 manage.py runserver 0.0.0.0:8000 &

# Wait a few seconds to ensure backend is up
sleep 5

echo "Starting React frontend on :3000..."
cd /opt/app/frontend

# Start React dev server
yarn dev --host 0.0.0.0 --port 3000
