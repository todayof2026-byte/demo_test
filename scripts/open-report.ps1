<#
.SYNOPSIS
  Open the already-built Allure HTML report in a local HTTP server.

.DESCRIPTION
  Allure reports cannot be opened directly via file:// because the static
  HTML loads its widgets / test data via XHR and browsers block AJAX from
  file:// origins. `allure open` spawns a tiny static-file server and
  pops your default browser at the right URL.

  This script targets a previously-built static report at
  `reports\allure-html\`. To rebuild from raw results, run
  `.\scripts\build-report.ps1` first.
#>

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not (Test-Path "reports\allure-html\index.html")) {
        Write-Host "No built report at reports\allure-html\." -ForegroundColor Yellow
        Write-Host "Build it first:  .\scripts\build-report.ps1" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Launching Allure HTTP server (Ctrl+C to stop)..." -ForegroundColor Cyan
    allure open "reports/allure-html"
}
finally {
    Pop-Location
}
