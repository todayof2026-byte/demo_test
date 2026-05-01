<#
.SYNOPSIS
  One-shot setup helper: install sops + age, generate an age key, print the public half.

.DESCRIPTION
  Run this ONCE per machine to bootstrap the encrypted-secrets workflow.
  Idempotent: if tools are already installed or a key already exists, it skips.

.PREREQUISITES
  - winget  (Windows 10 1809+ - included by default on modern Windows 11)
    OR scoop / choco - this script tries winget first.

.EXAMPLE
  .\scripts\setup-secrets.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# --- 1. sops -----------------------------------------------------------------
if (Has "sops") {
  Write-Host "sops already installed: $((sops --version) -join ' ')" -ForegroundColor Green
} else {
  Write-Host "Installing sops via winget..." -ForegroundColor Cyan
  winget install --id Mozilla.SOPS -e --accept-package-agreements --accept-source-agreements
}

# --- 2. age ------------------------------------------------------------------
if (Has "age" -and (Has "age-keygen")) {
  Write-Host "age already installed: $(age --version)" -ForegroundColor Green
} else {
  Write-Host "Installing age via winget..." -ForegroundColor Cyan
  winget install --id FiloSottile.age -e --accept-package-agreements --accept-source-agreements
}

Write-Host ""
Write-Host "Re-open PowerShell if 'sops' or 'age' are not yet on PATH, then re-run this script."

if (-not (Has "age-keygen")) { Write-Host "(age-keygen not on PATH yet - re-run after restart)"; return }

# --- 3. Generate an age key if missing --------------------------------------
$keyDir  = Join-Path $env:USERPROFILE ".config\sops\age"
$keyFile = Join-Path $keyDir "keys.txt"

if (-not (Test-Path $keyFile)) {
  if (-not (Test-Path $keyDir)) { New-Item -ItemType Directory -Path $keyDir | Out-Null }
  Write-Host "Generating new age keypair at $keyFile" -ForegroundColor Cyan
  age-keygen -o $keyFile
} else {
  Write-Host "Existing age key found at $keyFile" -ForegroundColor Green
}

# --- 4. Print the public key the user should paste into .sops.yaml ----------
$pub = (Get-Content -LiteralPath $keyFile | Select-String '# public key:' | ForEach-Object { ($_ -split ': ')[1].Trim() }) | Select-Object -First 1

if (-not $pub) {
  Write-Warning "Could not extract the public key from $keyFile. Open it manually; the line starts with '# public key: age1...'"
  return
}

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Yellow
Write-Host " Your age PUBLIC key (safe to commit, paste into .sops.yaml):"  -ForegroundColor Yellow
Write-Host "==============================================================" -ForegroundColor Yellow
Write-Host $pub -ForegroundColor White
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit .sops.yaml and replace the placeholder under 'age:' with the key above."
Write-Host "  2. Make sure .env has your real SITE_EMAIL / SITE_PASSWORD."
Write-Host "  3. Run:   .\scripts\encrypt-env.ps1"
Write-Host "  4. Commit secrets\credentials.sops.yaml and .sops.yaml. Never commit .env."
Write-Host ""
