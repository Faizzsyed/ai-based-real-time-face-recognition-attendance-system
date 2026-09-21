#!/usr/bin/env bash
# Start script for Production
set -e

echo "Starting AttendAI Backend in Production Mode..."
export APP_ENV=production

# The --proxy-headers flag tells Uvicorn to trust headers sent by the reverse proxy (like X-Forwarded-Proto)
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
