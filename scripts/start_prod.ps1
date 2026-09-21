# Start script for Production
$ErrorActionPreference = "Stop"

Write-Host "Starting AttendAI Backend in Production Mode..." -ForegroundColor Green
$env:APP_ENV = "production"

$port = if ($env:PORT) { $env:PORT } else { "8000" }

# The --proxy-headers flag tells Uvicorn to trust headers sent by the reverse proxy
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $port --proxy-headers
