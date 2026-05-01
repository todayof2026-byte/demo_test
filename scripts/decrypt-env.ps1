<#
.SYNOPSIS
  Decrypts secrets/credentials.sops.yaml into a local .env file.

.DESCRIPTION
  Inverse of encrypt-env.ps1. Reads the encrypted YAML and writes a plaintext
  .env at the repo root. Run this after cloning the repo and after placing
  your private age key at $env:USERPROFILE\.config\sops\age\keys.txt.

  The .env file is gitignored - it never leaves your machine.

.PREREQUISITES
  - sops on PATH (winget install Mozilla.SOPS  OR  scoop install sops)
  - age on PATH  (winget install FiloSottile.age OR  scoop install age)
  - Your private age key at:
        $env:USERPROFILE\.config\sops\age\keys.txt
    The public half of that key must be listed in .sops.yaml.

.EXAMPLE
  .\scripts\decrypt-env.ps1
#>

[CmdletBinding()]
param(
  [string]$SopsPath = (Join-Path $PSScriptRoot "..\secrets\credentials.sops.yaml"),
  [string]$EnvPath  = (Join-Path $PSScriptRoot "..\.env"),
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Require-Tool($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Error "Required tool '$name' not found on PATH. See script header for install hints."
    exit 1
  }
}

Require-Tool "sops"

if (-not (Test-Path $SopsPath)) {
  Write-Error "Encrypted file $SopsPath not found. Have you run scripts\encrypt-env.ps1 yet?"
  exit 1
}

if ((Test-Path $EnvPath) -and -not $Force) {
  Write-Warning "$EnvPath already exists. Use -Force to overwrite."
  exit 1
}

$decrypted = & sops --decrypt --input-type yaml --output-type yaml $SopsPath
if (-not $decrypted) { Write-Error "sops returned no output."; exit 1 }

# Parse the YAML output without a YAML library (we own the schema).
$email    = ""
$password = ""
foreach ($line in ($decrypted -split "`n")) {
  $trim = $line.Trim()
  if ($trim -match '^email:\s*(.+)$')    { $email    = $Matches[1].Trim() }
  if ($trim -match '^password:\s*(.+)$') { $password = $Matches[1].Trim() }
}

if (-not $email -or -not $password) {
  Write-Error "Could not extract email/password from decrypted secrets. Is the schema correct?"
  exit 1
}

# Preserve any pre-existing non-secret .env settings (PROFILE, HEADED, etc.).
$preserved = @()
if (Test-Path $EnvPath) {
  foreach ($line in Get-Content -LiteralPath $EnvPath) {
    if ($line -match '^\s*(SITE_EMAIL|SITE_PASSWORD)\s*=') { continue }
    $preserved += $line
  }
}

# Build the new .env body.
$header = @(
  "# Auto-written by scripts\decrypt-env.ps1 from secrets\credentials.sops.yaml.",
  "# DO NOT COMMIT THIS FILE. It is gitignored.",
  "SITE_EMAIL=$email",
  "SITE_PASSWORD=$password"
)
($header + "" + $preserved) | Set-Content -LiteralPath $EnvPath -Encoding utf8

Write-Host "Wrote plaintext credentials to $EnvPath" -ForegroundColor Green
Write-Host "Reminder: .env is gitignored. Do not commit it." -ForegroundColor Yellow
