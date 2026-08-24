$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & "$root\.venv\Scripts\python.exe" -m app.main
} finally {
    Pop-Location
}
