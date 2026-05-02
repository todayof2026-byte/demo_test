<#
.SYNOPSIS
  Run an arbitrary test (or any pytest target) preceded by the login test.

.DESCRIPTION
  Many of the project's tests can run standalone - the ``logged_in_page``
  fixture re-authenticates before the test body runs. But the brief asks
  that the LOGIN TEST itself be visible at the top of every run, so a
  reviewer always sees a recognisable "auth happens here" entry in the
  Allure report.

  This wrapper prepends ``tests/test_login.py`` to whatever pytest
  arguments you pass and runs the combined target through pytest.

.PARAMETER Target
  The pytest target to run (file, dir, or nodeid). Mandatory.

.NOTES
  Any arguments after ``-Target`` are forwarded verbatim to pytest.
  Use them for ``-k <expr>``, ``--headed=true``, ``--maxfail=1``, etc.

.EXAMPLE
  # Login + the e2e purchase flow:
  .\scripts\run-with-login.ps1 -Target tests/test_e2e_purchase_flow.py

  # Login + just the 'tshirt' data-driven scenario, headed:
  .\scripts\run-with-login.ps1 -Target tests/test_search_data_driven.py -k full_results_tshirt --headed=true
#>

# We declare ``$Target`` as a typed param but read pytest passthrough
# arguments off the automatic ``$args`` variable, which survives the
# ``powershell -File`` invocation path that ``[string[]] $ExtraArgs``
# does not. Net effect: callers can write
#   .\scripts\run-with-login.ps1 -Target tests/foo.py -k myscenario
# and -k / --headed flags reach pytest unchanged.

[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory = $true)]
    [string] $Target,

    # Anything else on the command line - typically pytest options like
    # -k, --headed=true, --maxfail=1 - is collected here and forwarded
    # to pytest. ``ValueFromRemainingArguments`` is the PowerShell-blessed
    # way to do "the rest of argv"; without it, the parameter binder
    # would error on the first unrecognised flag.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $env:PYTHONUNBUFFERED = "1"

    # Always ensure login test is first; skip duplication if caller already passed it.
    $loginTarget = "tests/test_login.py"
    $targets = if ($Target -eq $loginTarget) { @($loginTarget) } else { @($loginTarget, $Target) }

    $alluredir = "reports/allure-results"

    Write-Host "Run order (login first):" -ForegroundColor Cyan
    foreach ($t in $targets) { Write-Host "  - $t" -ForegroundColor Cyan }
    if ($PytestArgs -and $PytestArgs.Count -gt 0) {
        Write-Host "Pytest passthrough: $($PytestArgs -join ' ')" -ForegroundColor DarkCyan
    }
    Write-Host ""

    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }

    if ($PytestArgs -and $PytestArgs.Count -gt 0) {
        & $pythonExe -u -m pytest @targets -v --alluredir=$alluredir @PytestArgs
    } else {
        & $pythonExe -u -m pytest @targets -v --alluredir=$alluredir
    }
    $rc = $LASTEXITCODE

    Write-Host ""
    if ($rc -eq 0) {
        Write-Host "Run passed." -ForegroundColor Green
        Write-Host "Build the HTML report:  .\scripts\build-report.ps1" -ForegroundColor Cyan
        Write-Host "Open the HTML report :  .\scripts\open-report.ps1" -ForegroundColor Cyan
    } else {
        Write-Host "Run finished with exit code $rc." -ForegroundColor Yellow
    }
    exit $rc
}
finally {
    Pop-Location
}
