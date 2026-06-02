# ============================================================
# Agile Business -- PowerShell Launcher (Windows / Cross-platform)
# Usage: Right-click -> "Run with PowerShell"
#    or: powershell -ExecutionPolicy Bypass -File start.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Agile Business -- PowerShell Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Forward to Python launcher if available
$pyCmd = $null
foreach ($name in @("python3", "python")) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    if ($found) {
        $ver = & $name --version 2>&1
        if ($ver -match "Python 3") {
            $pyCmd = $name
            break
        }
    }
}

if ($pyCmd) {
    Write-Host "[OK] $pyCmd found" -ForegroundColor Green
    & $pyCmd start.py @args
    exit $LASTEXITCODE
}

# No Python -- try Docker directly
Write-Host "[!] Python not found, trying Docker directly..." -ForegroundColor Yellow

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host ""
    Write-Host "[ERROR] Neither Python nor Docker found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install one of:" -ForegroundColor Yellow
    Write-Host "  Python 3.10+:     https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  Docker Desktop:   https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check/create .env
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env with local defaults..." -ForegroundColor Yellow
    $secret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
    @"
DEBUG=false
SECRET_KEY=$secret
DOMAIN=localhost
DB_PASSWORD=agile_local_pass
REDIS_PASSWORD=agile_redis_pass
MINIO_USER=minioadmin
MINIO_PASSWORD=minioadmin123
ELASTIC_PASSWORD=changeme
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
ADMIN_SEED_EMAIL=admin@agile.local
ADMIN_SEED_PASSWORD=admin123
WORKERS=2
FRONTEND_PORT=3000
"@ | Set-Content ".env" -Encoding UTF8
    Write-Host "[OK] .env created" -ForegroundColor Green
}

Write-Host "Starting with Docker Compose..." -ForegroundColor Cyan
docker compose up -d --build --remove-orphans

Write-Host ""
Write-Host "Waiting for site to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Open browser
$url = "http://localhost:3000"
Write-Host "Opening browser: $url" -ForegroundColor Green
Start-Process $url

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Site running at $url" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Keep alive
try {
    while ($true) { Start-Sleep -Seconds 10 }
} finally {
    Write-Host "Stopping containers..." -ForegroundColor Yellow
    docker compose down
}
