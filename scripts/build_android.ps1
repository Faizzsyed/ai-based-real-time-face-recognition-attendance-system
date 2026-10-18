param(
    [ValidateSet("apk", "aab")]
    [string]$Target = "apk",
    [string]$ApiUrl = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = "$root\.venv\Scripts\python.exe"

$flutterBin = "C:\Users\Faiz\flutter\3.44.8\bin"
if (-not (Test-Path "$flutterBin\flutter.bat")) {
    throw "Expected Flet Flutter SDK was not found at $flutterBin."
}

$buildConfigPath = "$PSScriptRoot\..\app\core\build_config.py"
$projectPath = "$root\app\pyproject.toml"
$projectBytes = [IO.File]::ReadAllBytes($projectPath)
$previousConfig = if (Test-Path -LiteralPath $buildConfigPath) { [IO.File]::ReadAllBytes($buildConfigPath) } else { $null }
$previousPath = $env:PATH
$previousEncoding = $env:PYTHONIOENCODING
$output = Join-Path $PSScriptRoot "..\app\build\android\$Target"
try {
    # Use the same URL policy as the runtime; never print unvalidated input.
    $normalizedApiUrl = & $python "$PSScriptRoot\prepare_android_config.py" --api-url $ApiUrl --output $buildConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Invalid Android API configuration. Provide -ApiUrl with a LAN or HTTPS backend URL." }
    Write-Host "Android API configuration validated."
    $projectText = [Text.Encoding]::UTF8.GetString($projectBytes)
    $pattern = '(?m)^usesCleartextTraffic\s*=\s*"false"\s*$'
    if ([regex]::Matches($projectText, $pattern).Count -ne 1) {
        throw 'Expected exactly one usesCleartextTraffic = "false" secure default in app/pyproject.toml.'
    }
    if ($normalizedApiUrl.StartsWith("http://")) {
        Write-Warning "Development HTTP build: use HTTPS for production."
        [IO.File]::WriteAllText($projectPath, [regex]::Replace($projectText, $pattern, 'usesCleartextTraffic = "true"'), [Text.UTF8Encoding]::new($false))
    }
    $env:PATH = "$flutterBin;$previousPath"
    $env:PYTHONIOENCODING = "utf-8"
    & "$PSScriptRoot\..\.venv\Scripts\flet.exe" build $Target "$PSScriptRoot\..\app" `
        --arch arm64-v8a `
        --project attendai `
        --product "AI Attendance" `
        --org com.faizzsyed `
        --permissions camera photo_library `
        --no-compile-app `
        --output $output `
        --yes
    if ($LASTEXITCODE -ne 0) { throw "Flet Android build failed (exit $LASTEXITCODE)." }
    & $python "$PSScriptRoot\verify_android_package.py" "$output\attendai.$Target" --api-url $normalizedApiUrl
    if ($LASTEXITCODE -ne 0) { throw "Packaged Android configuration verification failed." }
} finally {
    [IO.File]::WriteAllBytes($projectPath, $projectBytes)
    if ($null -ne $previousConfig) {
        [IO.File]::WriteAllBytes($buildConfigPath, $previousConfig)
    } elseif (Test-Path -LiteralPath $buildConfigPath) {
        Remove-Item -LiteralPath $buildConfigPath -Force
    }
    $env:PATH = $previousPath
    $env:PYTHONIOENCODING = $previousEncoding
}
