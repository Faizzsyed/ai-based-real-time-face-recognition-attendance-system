param(
    [ValidateSet("apk", "aab")]
    [string]$Target = "apk"
)

$flutterBin = "C:\Users\Faiz\flutter\3.44.8\bin"
if (-not (Test-Path "$flutterBin\flutter.bat")) {
    throw "Expected Flet Flutter SDK was not found at $flutterBin."
}

$env:PATH = "$flutterBin;$env:PATH"
$output = Join-Path $PSScriptRoot "..\app\build\android\$Target"
& "$PSScriptRoot\..\.venv\Scripts\flet.exe" build $Target "$PSScriptRoot\..\app" `
    --arch arm64-v8a `
    --project attendai `
    --product "AI Attendance" `
    --org com.faizzsyed `
    --permissions camera photo_library `
    --output $output `
    --yes
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
