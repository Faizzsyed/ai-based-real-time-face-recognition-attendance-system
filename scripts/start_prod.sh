#!/usr/bin/env bash
# Start script for Production
set -e

echo "Starting AttendAI Backend in Production Mode..."
export APP_ENV=production

# The --proxy-headers flag tells Uvicorn to trust headers sent by the reverse proxy (like X-Forwarded-Proto)
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python -m uvicorn app.main:app --app-dir "$root/backend" --host "${API_HOST:-0.0.0.0}" --port "${PORT:-${API_PORT:-8000}}" --proxy-headers
