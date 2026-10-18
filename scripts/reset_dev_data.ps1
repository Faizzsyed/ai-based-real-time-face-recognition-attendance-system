$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    Write-Host 'AttendAI development reset - enter credentials only in this window.' -ForegroundColor Cyan
    & "$root\.venv\Scripts\python.exe" "$root\backend\scripts\reset_dev_data.py"
    Write-Host "Reset process exit code: $LASTEXITCODE"
    Read-Host 'Press Enter to close this reset window'
} finally {
    Pop-Location
}
