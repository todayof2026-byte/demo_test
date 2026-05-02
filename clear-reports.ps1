#requires -Version 5.1
<#
.SYNOPSIS
    Wipe all reports/evidence/login artefacts so the next test run produces a
    pristine, single-run deliverable.

.DESCRIPTION
    Deletes:
        reports/allure-results/   (raw Allure JSON)
        reports/allure-html/      (built static HTML report)
        reports/evidence/         (per-test trace.zip / video.webm / log.txt / screenshots)
        reports/login-evidence/   (sanitised login screenshot from make_login_evidence.py)
        reports/junit.xml         (JUnit XML)
        reports/*.log, reports/*.err  (pytest stdout / stderr captures)
        .auth/storage_state.json  (cached login -> forces a fresh login next run)

    Leaves alone:
        reports/.gitkeep (if present)
        Anything outside reports/ and .auth/

.EXAMPLE
    PS> .\clear-reports.ps1
    Removes all run artefacts, prints a summary.

.EXAMPLE
    PS> .\clear-reports.ps1 -DryRun
    Lists what WOULD be deleted without touching anything.

.EXAMPLE
    PS> .\clear-reports.ps1 -KeepStorageState
    Keeps the cached login session (skip the .auth/ wipe).
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$KeepStorageState,
    [switch]$KeepProcesses,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Write-Info {
    param([string]$msg, [string]$color = 'Gray')
    if (-not $Quiet) { Write-Host $msg -ForegroundColor $color }
}

# --------------------------------------------------------------- pre-flight kill
# Wipe leftover browser / test runners before deleting their report files.
# pytest-playwright sometimes leaves zombie chrome workers around when a run
# is killed mid-teardown; those zombies hold handles into the .auth/ and
# evidence/ folders, which causes "file in use" errors on Remove-Item.
# Killing them first makes the cleanup deterministic.
if (-not $KeepProcesses) {
    $killNames = @('chrome', 'chromium', 'msedgewebview2', 'node', 'playwright')
    $killed = 0
    foreach ($n in $killNames) {
        $procs = Get-Process -Name $n -ErrorAction SilentlyContinue
        if ($procs) {
            $killed += $procs.Count
            if (-not $DryRun) {
                $procs | Stop-Process -Force -ErrorAction SilentlyContinue
            }
        }
    }
    # Pythons that look like stuck pytest workers (don't kill the IDE's LSP).
    $pyPids = @(
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'pytest' -and $_.ProcessId -ne $PID }
    )
    if ($pyPids.Count -gt 0) {
        $killed += $pyPids.Count
        if (-not $DryRun) {
            $pyPids | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    if ($killed -gt 0) {
        $verb = if ($DryRun) { 'WOULD kill' } else { 'killed' }
        Write-Info ("  {0,-17}: {1} stale browser/pytest process(es)" -f $verb, $killed) 'DarkGray'
    }
    Start-Sleep -Milliseconds 300
}

# Targets: each entry is { Path, Kind } where Kind = 'dir' | 'file' | 'glob'.
$targets = @(
    @{ Path = 'reports/allure-results';  Kind = 'dir'  },
    @{ Path = 'reports/allure-html';     Kind = 'dir'  },
    @{ Path = 'reports/evidence';        Kind = 'dir'  },
    @{ Path = 'reports/login-evidence';  Kind = 'dir'  },
    @{ Path = 'reports/junit.xml';       Kind = 'file' },
    @{ Path = 'reports/*.log';           Kind = 'glob' },
    @{ Path = 'reports/*.err';           Kind = 'glob' }
)

if (-not $KeepStorageState) {
    $targets += @{ Path = '.auth/storage_state.json'; Kind = 'file' }
}

Write-Info ''
if ($DryRun) {
    Write-Info '== Clear reports (DRY RUN - nothing will be deleted) ==' 'Yellow'
} else {
    Write-Info '== Clear reports ==' 'Cyan'
}
Write-Info "Repo root: $root" 'DarkGray'
Write-Info ''

$totalFiles = 0
$totalBytes = 0L

foreach ($t in $targets) {
    $p = $t.Path
    $kind = $t.Kind

    switch ($kind) {
        'dir' {
            if (Test-Path -LiteralPath $p -PathType Container) {
                $items = Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue
                $count = ($items | Measure-Object).Count
                $bytes = ($items | Measure-Object Length -Sum).Sum
                if (-not $bytes) { $bytes = 0 }
                $totalFiles += $count
                $totalBytes += $bytes
                $sizeMB = [math]::Round($bytes / 1MB, 2)
                if ($DryRun) {
                    Write-Info "  WOULD remove dir : $p  ($count files, $sizeMB MB)" 'Yellow'
                } else {
                    Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
                    Write-Info "  removed dir      : $p  ($count files, $sizeMB MB)" 'Green'
                }
            } else {
                Write-Info "  skipped (missing): $p" 'DarkGray'
            }
        }
        'file' {
            if (Test-Path -LiteralPath $p -PathType Leaf) {
                $f = Get-Item -LiteralPath $p
                $totalFiles += 1
                $totalBytes += $f.Length
                if ($DryRun) {
                    Write-Info "  WOULD remove file: $p  ($($f.Length) bytes)" 'Yellow'
                } else {
                    Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
                    Write-Info "  removed file     : $p" 'Green'
                }
            } else {
                Write-Info "  skipped (missing): $p" 'DarkGray'
            }
        }
        'glob' {
            $globMatches = @(Get-ChildItem -Path $p -File -ErrorAction SilentlyContinue)
            if ($globMatches.Count -gt 0) {
                foreach ($m in $globMatches) {
                    $totalFiles += 1
                    $totalBytes += $m.Length
                    if ($DryRun) {
                        Write-Info "  WOULD remove file: $($m.FullName)" 'Yellow'
                    } else {
                        Remove-Item -LiteralPath $m.FullName -Force -ErrorAction SilentlyContinue
                        Write-Info "  removed file     : $($m.FullName)" 'Green'
                    }
                }
            } else {
                Write-Info "  skipped (no match): $p" 'DarkGray'
            }
        }
    }
}

# Recreate the empty reports/ folder so subsequent tools don't choke on a
# missing directory. allure-results/ and evidence/ are created lazily by
# pytest / Allure, so we don't pre-create those.
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path 'reports' | Out-Null
}

$totalMB = [math]::Round($totalBytes / 1MB, 2)
Write-Info ''
if ($DryRun) {
    Write-Info "Done (DRY RUN). Would delete $totalFiles files / $totalMB MB." 'Yellow'
} else {
    Write-Info "Done. Deleted $totalFiles files / $totalMB MB." 'Cyan'
    Write-Info "Tip: run scripts\run-suite.ps1 to produce a fresh single set of results." 'DarkGray'
}
Write-Info ''
