param(
    [string]$BindAddress = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port already has a listener (PID $($listener[0].OwningProcess), address $($listener[0].LocalAddress)). Stop the existing backend in its terminal with Ctrl+C, then rerun this script. No duplicate backend was started."
}
Push-Location $root
try {
    $uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--app-dir', "$root\backend", '--host', $BindAddress, '--port', $Port)
    if (-not $NoReload) { $uvicornArgs += @('--reload', '--reload-dir', "$root\backend\app") }
    & "$root\.venv\Scripts\python.exe" @uvicornArgs
} finally {
    Pop-Location
}
