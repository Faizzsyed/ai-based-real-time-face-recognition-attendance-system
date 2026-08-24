$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & "$root\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "$root\backend" --host 127.0.0.1 --port 8000 --reload
} finally {
    Pop-Location
}
