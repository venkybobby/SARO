<#
.SYNOPSIS
  One-shot local bring-up for SARO: Postgres (Docker) + FastAPI backend + Vite frontend,
  with demo data seeded. Open http://localhost:5173 and log in with the demo account.

.DESCRIPTION
  Why this script exists (see memory/project_local_run_recipe.md):
    - database.py REQUIRES a DATABASE_URL and forces sslmode=require by default
      (config.py db_sslmode) — a local Postgres has no SSL, so we set DB_SSLMODE=disable.
    - The host may already have a NATIVE Windows postgres.exe AND/or a legacy
      "saro-platform" Docker stack bound to :5432. To avoid that ambiguity we run a
      DEDICATED Postgres container on a clean port (5544 by default).
    - The backend self-migrates on startup (apply_pending_migrations 000..021) and
      seeds demo data when SEED_DEMO_DATA=true. The fresh-Postgres migration chain is
      fixed (FND-011/FND-012), so no manual schema_migrations bypass is needed.
    - The Vite dev server proxies /api -> http://localhost:8000, so the browser talks
      to the backend through the dev server. (Do NOT use `docker compose up` for the web
      tier — that compose frontend is misconfigured.)

  Re-runnable: reuses the DB container if it already exists. Use -Reset to wipe the
  database and reseed from scratch.

.PARAMETER Reset
  Drop and recreate the Postgres container (destroys local demo data, forces a fresh seed).

.PARAMETER DbPort
  Host port for the dedicated Postgres container. Default 5544 (avoids the :5432 collision).

.PARAMETER ApiPort
  Host port for the FastAPI backend. Default 8000 (the Vite proxy target).

.EXAMPLE
  pwsh ./scripts/run_local.ps1
.EXAMPLE
  pwsh ./scripts/run_local.ps1 -Reset
#>
[CmdletBinding()]
param(
    [switch]$Reset,
    [int]$DbPort = 5544,
    [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DbName        = "saro-local-db"
$DbUser        = "saro"
$DbPassword    = "saro_local_dev"
$DbDatabase    = "saro"
$DatabaseUrl   = "postgresql://${DbUser}:${DbPassword}@localhost:${DbPort}/${DbDatabase}"
$DemoEmail     = "demo@saro-demo.internal"
$DemoPassword  = "SaroDemo2026!"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ── 0. Prerequisites ─────────────────────────────────────────────────────────
Write-Step "Checking prerequisites"
foreach ($exe in @("docker", "python", "npm")) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "$exe not found on PATH. Install it (Docker Desktop / Python / Node) and retry."
    }
}
try { docker info *> $null } catch { throw "Docker daemon is not running. Start Docker Desktop and retry." }

# ── 1. Postgres (dedicated container on a clean port) ────────────────────────
Write-Step "Postgres container '$DbName' on host port $DbPort"
$existing = (docker ps -aq -f "name=^$DbName$")
if ($Reset -and $existing) {
    Write-Host "  -Reset: removing existing '$DbName'"
    docker rm -f $DbName *> $null
    $existing = $null
}
if (-not $existing) {
    docker run -d --name $DbName -p "${DbPort}:5432" `
        -e POSTGRES_USER=$DbUser -e POSTGRES_PASSWORD=$DbPassword -e POSTGRES_DB=$DbDatabase `
        postgres:16-alpine | Out-Null
    Write-Host "  created"
} else {
    docker start $DbName *> $null
    Write-Host "  reusing existing container"
}

Write-Host "  waiting for Postgres to accept connections..."
$ready = $false
foreach ($i in 1..30) {
    docker exec $DbName pg_isready -U $DbUser -d $DbDatabase *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw "Postgres did not become ready on port $DbPort." }
Write-Host "  ready"

# ── 2. Backend (uvicorn) — self-migrates + seeds on startup ──────────────────
Write-Step "Starting FastAPI backend on http://localhost:$ApiPort"
$backendEnv = @{
    DATABASE_URL                 = $DatabaseUrl
    DB_SSLMODE                   = "disable"
    JWT_SECRET_KEY               = "local-dev-secret-change-in-prod"
    JWT_ALGORITHM                = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES  = "1440"
    SEED_DEMO_DATA               = "true"
    ENV                          = "development"
}
$envPrefix = ($backendEnv.GetEnumerator() | ForEach-Object { "`$env:$($_.Key)='$($_.Value)';" }) -join " "
$backendCmd = "$envPrefix Set-Location '$RepoRoot'; python -m uvicorn main:app --host 0.0.0.0 --port $ApiPort"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd | Out-Null

Write-Host "  waiting for /health (migrations + demo seed run on first boot, ~30-60s)..."
$healthy = $false
foreach ($i in 1..45) {
    try {
        $h = Invoke-RestMethod -Uri "http://localhost:$ApiPort/health" -TimeoutSec 3 -ErrorAction Stop
        if ($h.database -eq "ok") { $healthy = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    Write-Warning "Backend did not report database:ok yet. Check the backend window for migration/seed errors."
} else {
    Write-Host "  backend healthy (schema_version reported by /health)" -ForegroundColor Green
}

# ── 3. Frontend (Vite dev server, proxies /api -> backend) ───────────────────
Write-Step "Starting Vite frontend on http://localhost:5173"
$frontendDir = Join-Path $RepoRoot "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "  installing frontend deps (npm install)..."
    Push-Location $frontendDir; npm install; Pop-Location
}
$frontendCmd = "Set-Location '$frontendDir'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd | Out-Null

# ── 4. Done ──────────────────────────────────────────────────────────────────
Write-Step "SARO is starting"
Write-Host ""
Write-Host "  Open:     http://localhost:5173" -ForegroundColor Green
Write-Host "  Email:    $DemoEmail"
Write-Host "  Password: $DemoPassword"
Write-Host ""
Write-Host "  Backend:  http://localhost:$ApiPort/health   (runs in its own window)"
Write-Host "  Database: $DbName (Docker, host port $DbPort)"
Write-Host ""
Write-Host "  Stop:     close the two PowerShell windows; 'docker stop $DbName' to stop the DB"
Write-Host "  Reseed:   pwsh ./scripts/run_local.ps1 -Reset"
Write-Host ""
