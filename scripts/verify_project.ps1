$root = Split-Path -Parent $PSScriptRoot
$python = "$root\.venv\Scripts\python.exe"
& $python -m compileall -q "$root\backend" "$root\app"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest "$root\backend\tests" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Push-Location "$root\backend"
try {
    & $python -c "import app.main; print('backend import ok')"
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Push-Location $root
try {
    & $python -c "import app.main; print('flet import ok')"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m pytest "$root\app" -q
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
