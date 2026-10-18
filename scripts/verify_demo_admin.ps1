param([Parameter(Mandatory=$true)][string]$ApiUrl, [switch]$ResetPassword)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $Host.UI.RawUI.WindowTitle = if ($ResetPassword) { 'AttendAI - SET NEW ADMIN PASSWORD' } else { 'AttendAI - VERIFY ADMIN LOGIN' }
    Clear-Host
    Write-Host $Host.UI.RawUI.WindowTitle -ForegroundColor Cyan
    Write-Host 'Account: demo.admin. Password input is hidden; type normally, then press Enter.'
    $verifyArgs = @("$root\backend\scripts\verify_demo_admin.py", '--api-url', $ApiUrl)
    if ($ResetPassword) { $verifyArgs += '--reset-password' }
    & "$root\.venv\Scripts\python.exe" @verifyArgs
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'PASS - Admin login, identity, refresh and logout verified.' -ForegroundColor Green
    } else {
        Write-Host 'FAILED - The Admin login was not verified. See the local messages above.' -ForegroundColor Red
    }
    Read-Host 'Press Enter to close this verification window'
} finally {
    Pop-Location
}
