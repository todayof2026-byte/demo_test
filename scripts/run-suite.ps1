<#
.SYNOPSIS
  Run the full E2E suite in brief order: login -> e2e purchase flow -> data-driven search.

.DESCRIPTION
  pytest collects test files alphabetically by default, which means the
  login test (test_login.py) would run AFTER test_e2e_purchase_flow.py.
  This wrapper makes the order match the brief's narrative order:

      1. test_login.py                     - authentication
      2. test_e2e_purchase_flow.py         - search + add + assert
      3. test_search_data_driven.py        - data-driven search scenarios

  Each subsequent test still re-authenticates via the ``logged_in_page``
  fixture (so they remain runnable standalone), but the SUITE order keeps
  the Allure timeline reading top-to-bottom in the same order as the
  brief's bullet list.

.NOTES
  Any extra arguments after the standard ones are forwarded verbatim to
  pytest. Useful for ``--headed=true``, ``-k <expr>``, ``--maxfail=1``, etc.

.EXAMPLE
  .\scripts\run-suite.ps1
  .\scripts\run-suite.ps1 -k tshirt --maxfail=1
  .\scripts\run-suite.ps1 --headed=true
#>

[CmdletBinding(PositionalBinding = $false)]
param(
    # Any pytest options (e.g. -k, --headed=true, --maxfail=1) are collected
    # here and forwarded as-is. ``ValueFromRemainingArguments`` makes the
    # PowerShell binder accept arbitrary flags without choking on unknown
    # parameter names, which is what callers naturally type.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $env:PYTHONUNBUFFERED = "1"

    $orderedTargets = @(
        "tests/test_login.py",
        "tests/test_e2e_purchase_flow.py",
        "tests/test_search_data_driven.py"
    )

    $alluredir = "reports/allure-results"
    Write-Host "Running suite in brief order:" -ForegroundColor Cyan
    foreach ($t in $orderedTargets) { Write-Host "  - $t" -ForegroundColor Cyan }
    Write-Host ""

    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = "python"  # fall back to PATH
    }

    if ($PytestArgs -and $PytestArgs.Count -gt 0) {
        & $pythonExe -u -m pytest @orderedTargets -v --alluredir=$alluredir @PytestArgs
    } else {
        & $pythonExe -u -m pytest @orderedTargets -v --alluredir=$alluredir
    }
    $rc = $LASTEXITCODE

    Write-Host ""
    if ($rc -eq 0) {
        Write-Host "All suite tests passed." -ForegroundColor Green
        Write-Host "Build the HTML report:  .\scripts\build-report.ps1" -ForegroundColor Cyan
        Write-Host "Open the HTML report :  .\scripts\open-report.ps1" -ForegroundColor Cyan
    } else {
        Write-Host "Suite finished with exit code $rc." -ForegroundColor Yellow
    }
    exit $rc
}
finally {
    Pop-Location
}
