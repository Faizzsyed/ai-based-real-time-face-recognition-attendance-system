$root = Split-Path -Parent $PSScriptRoot
$python = "$root\.venv\Scripts\python.exe"
$previousPythonPath = $env:PYTHONPATH
$appSourcePaths = @("$root\app\main.py")
$appSourcePaths += Get-ChildItem -LiteralPath "$root\app" -Directory |
    Where-Object { $_.Name -notin @("build", ".gradle", "__pycache__") } |
    ForEach-Object { $_.FullName }
& $python -m compileall -q "$root\backend" $appSourcePaths
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
try {
    $env:PYTHONPATH = "$root\backend"
    & $python -m pytest "$root\backend\tests" -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -c "import app.main; print('backend import ok')"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $env:PYTHONPATH = $root
    & $python -c "import app.main; print('flet import ok')"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m pytest "$root\app" -q
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
