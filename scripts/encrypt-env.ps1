<#
.SYNOPSIS
  Encrypts the local .env file into secrets/credentials.sops.yaml using SOPS+age.

.DESCRIPTION
  Reads SITE_EMAIL and SITE_PASSWORD from the local (gitignored) .env file
  and writes an encrypted YAML into secrets/credentials.sops.yaml. The
  encrypted file IS safe to commit. The plaintext .env stays gitignored.

.PREREQUISITES
  - sops on PATH         (winget install Mozilla.SOPS  OR  scoop install sops)
  - age and age-keygen   (winget install FiloSottile.age  OR  scoop install age)
  - An age keypair at $env:USERPROFILE\.config\sops\age\keys.txt
    Create one with:    age-keygen -o $env:USERPROFILE\.config\sops\age\keys.txt
  - The PUBLIC age key pasted into .sops.yaml -> creation_rules[0].age

.EXAMPLE
  .\scripts\encrypt-env.ps1
#>

[CmdletBinding()]
param(
  [string]$EnvPath = (Join-Path $PSScriptRoot "..\.env"),
  [string]$OutPath = (Join-Path $PSScriptRoot "..\secrets\credentials.sops.yaml")
)

$ErrorActionPreference = "Stop"

function Require-Tool($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Error "Required tool '$name' not found on PATH. See script header for install hints."
    exit 1
  }
}

Require-Tool "sops"
Require-Tool "age"

if (-not (Test-Path $EnvPath)) {
  Write-Error "No .env file at $EnvPath. Copy .env.example to .env and fill in your credentials first."
  exit 1
}

# Parse the .env into a hashtable (very small subset: KEY=VALUE, ignore comments/blanks).
$envMap = @{}
foreach ($line in Get-Content -LiteralPath $EnvPath) {
  $trim = $line.Trim()
  if (-not $trim -or $trim.StartsWith("#")) { continue }
  $idx = $trim.IndexOf("=")
  if ($idx -lt 1) { continue }
  $key = $trim.Substring(0, $idx).Trim()
  $val = $trim.Substring($idx + 1).Trim().Trim('"').Trim("'")
  $envMap[$key] = $val
}

$email    = $envMap["SITE_EMAIL"]
$password = $envMap["SITE_PASSWORD"]

if (-not $email -or -not $password) {
  Write-Error "SITE_EMAIL or SITE_PASSWORD missing/empty in $EnvPath."
  exit 1
}

# Make sure the destination dir exists.
$outDir = Split-Path -Parent $OutPath
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

# Repo root (one level above the scripts/ folder where this script lives).
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

# Build a temporary plaintext YAML inside secrets/ so its path matches the
# creation_rules regex in .sops.yaml ("^secrets/.*\.sops\.(ya?ml|json|env)$").
# SOPS evaluates that regex against the INPUT path it received on the CLI,
# so we must:
#   1. cd into the repo root, and
#   2. pass a relative POSIX-style path ("secrets/foo.sops.yaml")
# Otherwise SOPS sees "C:\...\secrets\foo.sops.yaml" and the rule never matches.
$tmpName    = "credentials.staging.sops.yaml"
$tmpPath    = Join-Path $outDir $tmpName
$tmpRelPath = "secrets/$tmpName"
$plain = @"
site:
  email: $email
  password: $password
"@
Set-Content -LiteralPath $tmpPath -Value $plain -Encoding utf8

Push-Location $repoRoot
try {
  & sops --encrypt --in-place $tmpRelPath
  if ($LASTEXITCODE -ne 0) {
    throw "sops --encrypt --in-place failed (exit $LASTEXITCODE). See output above."
  }
  Move-Item -LiteralPath $tmpPath -Destination $OutPath -Force
} catch {
  if (Test-Path $tmpPath) { Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue }
  throw
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Encrypted -> $OutPath" -ForegroundColor Green
Write-Host "It is safe to commit this file. Plaintext .env stays gitignored." -ForegroundColor Green
