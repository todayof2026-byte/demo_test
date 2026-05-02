<#
.SYNOPSIS
  Launch an interactive Allure server and open it in the default browser.

.DESCRIPTION
  Wraps `allure serve`. The server is short-lived: it runs until you
  press Ctrl+C in this terminal. Use this for live exploration during
  development. For something portable to share, use build-report.ps1
  instead.
#>

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not (Test-Path "reports\allure-results")) {
        Write-Host "No allure results found at reports\allure-results." -ForegroundColor Yellow
        Write-Host "Run pytest first, e.g.:  pytest tests/test_login.py -v" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Launching Allure server (Ctrl+C to stop)..." -ForegroundColor Cyan
    allure serve "reports/allure-results"
}
finally {
    Pop-Location
}
