# Start script for Production
$ErrorActionPreference = "Stop"

Write-Host "Starting AttendAI Backend in Production Mode..." -ForegroundColor Green
$env:APP_ENV = "production"

$root = Split-Path -Parent $PSScriptRoot
$bindAddress = if ($env:API_HOST) { $env:API_HOST } else { "0.0.0.0" }
$port = if ($env:PORT) { $env:PORT } elseif ($env:API_PORT) { $env:API_PORT } else { "8000" }

# The --proxy-headers flag tells Uvicorn to trust headers sent by the reverse proxy
python -m uvicorn app.main:app --app-dir "$root\backend" --host $bindAddress --port $port --proxy-headers
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
