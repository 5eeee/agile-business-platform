# ============================================================
# Agile Business — Установка для локальной разработки (Windows)
# Запуск: правый клик → "Запустить с помощью PowerShell"
# или: powershell -ExecutionPolicy Bypass -File install-local.ps1
# ============================================================

param(
    [switch]$SkipDeps,    # Пропустить установку системных зависимостей
    [switch]$SkipDB,      # Пропустить создание БД
    [switch]$SkipFront    # Пропустить установку фронтенда
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Agile Business — Установка (Windows)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ——————————————— Функции ———————————————

function Write-Step($msg) {
    Write-Host ""
    Write-Host ">> $msg" -ForegroundColor Green
}

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Wait-ForKey {
    Write-Host ""
    Write-Host "Нажмите любую клавишу для продолжения..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# ——————————————— 1. Проверка зависимостей ———————————————

if (-not $SkipDeps) {
    Write-Step "1. Проверка системных зависимостей"

    $missing = @()

    if (-not (Test-Command "python")) { $missing += "Python" }
    else { Write-Host "  [OK] Python: $(python --version 2>&1)" -ForegroundColor DarkGreen }

    if (-not (Test-Command "node")) { $missing += "Node.js" }
    else { Write-Host "  [OK] Node.js: $(node --version)" -ForegroundColor DarkGreen }

    if (-not (Test-Command "pg_isready")) { $missing += "PostgreSQL" }
    else { Write-Host "  [OK] PostgreSQL установлен" -ForegroundColor DarkGreen }

    # Redis — проверяем и как сервис, и как файл
    $redisPath = "C:\Program Files\Redis\redis-server.exe"
    if (-not (Test-Command "redis-cli") -and -not (Test-Path $redisPath)) {
        $missing += "Redis"
    } else {
        Write-Host "  [OK] Redis установлен" -ForegroundColor DarkGreen
    }

    if ($missing.Count -gt 0) {
        Write-Host ""
        Write-Host "  ОТСУТСТВУЮТ:" -ForegroundColor Red
        foreach ($m in $missing) {
            Write-Host "    - $m" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "  Установите вручную:" -ForegroundColor Yellow
        Write-Host "    Python 3.11+:  https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "    Node.js 18+:   https://nodejs.org/" -ForegroundColor Yellow
        Write-Host "    PostgreSQL:    https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
        Write-Host "    Redis:         winget install Microsoft.Redis" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  После установки запустите скрипт снова." -ForegroundColor Yellow
        Wait-ForKey
        exit 1
    }
}

# ——————————————— 2. Python venv + зависимости ———————————————

Write-Step "2. Создание Python виртуального окружения"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Write-Host "  Создано .venv" -ForegroundColor DarkGreen
} else {
    Write-Host "  .venv уже существует" -ForegroundColor DarkGreen
}

& .\.venv\Scripts\Activate.ps1

Write-Step "3. Установка Python зависимостей"
pip install --upgrade pip --quiet
pip install -r server\requirements.txt --quiet
Write-Host "  Зависимости установлены" -ForegroundColor DarkGreen

# ——————————————— 3. Конфигурация .env ———————————————

Write-Step "4. Настройка конфигурации (server/.env)"

if (-not (Test-Path "server\.env")) {
    Copy-Item "server\.env.example" "server\.env"
    Write-Host "  Создан server/.env из шаблона" -ForegroundColor DarkGreen

    # Генерируем SECRET_KEY
    $secretKey = python -c "import secrets; print(secrets.token_urlsafe(32))"

    # Записываем базовые значения
    $envContent = @"
# ===== Agile Business — Local Development =====
DEBUG=true
SECRET_KEY=$secretKey
DOMAIN=localhost
DATABASE_URL=postgresql+asyncpg://agile:agile_pass@localhost:5432/agile_db
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=agile-files
ADMIN_SEED_EMAIL=admin@agile.com
ADMIN_SEED_PASSWORD=admin123
CORS_ORIGINS=["http://localhost:5173","http://localhost:5174","http://localhost:3000"]
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
TELEGRAM_WEBHOOK_SECRET=
"@
    Set-Content "server\.env" $envContent -Encoding UTF8
    Write-Host "  SECRET_KEY сгенерирован автоматически" -ForegroundColor DarkGreen
} else {
    Write-Host "  server/.env уже существует — пропускаем" -ForegroundColor DarkGreen
}

# ——————————————— 4. PostgreSQL — создание БД ———————————————

if (-not $SkipDB) {
    Write-Step "5. Создание базы данных PostgreSQL"

    $dbExists = $false
    try {
        $result = psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='agile_db'" 2>$null
        if ($result -match "1") { $dbExists = $true }
    } catch {}

    if ($dbExists) {
        Write-Host "  БД agile_db уже существует" -ForegroundColor DarkGreen
    } else {
        Write-Host "  Создаём пользователя и БД..." -ForegroundColor Yellow
        Write-Host "  (Может потребоваться пароль от postgres)" -ForegroundColor Yellow
        try {
            psql -U postgres -c "CREATE USER agile WITH PASSWORD 'agile_pass';" 2>$null
        } catch {
            Write-Host "  Пользователь agile уже существует" -ForegroundColor DarkGreen
        }
        try {
            psql -U postgres -c "CREATE DATABASE agile_db OWNER agile;" 2>$null
            Write-Host "  БД agile_db создана" -ForegroundColor DarkGreen
        } catch {
            Write-Host "  ОШИБКА при создании БД. Создайте вручную:" -ForegroundColor Red
            Write-Host '    psql -U postgres -c "CREATE USER agile WITH PASSWORD ''agile_pass'';"' -ForegroundColor Yellow
            Write-Host '    psql -U postgres -c "CREATE DATABASE agile_db OWNER agile;"' -ForegroundColor Yellow
        }
    }
}

# ——————————————— 5. Redis ———————————————

Write-Step "6. Проверка Redis"

$redisRunning = $false
try {
    $pong = redis-cli ping 2>$null
    if ($pong -eq "PONG") { $redisRunning = $true }
} catch {}

if ($redisRunning) {
    Write-Host "  Redis работает" -ForegroundColor DarkGreen
} else {
    Write-Host "  Redis не запущен. Запускаем..." -ForegroundColor Yellow
    $redisExe = "C:\Program Files\Redis\redis-server.exe"
    if (Test-Path $redisExe) {
        Start-Process -FilePath $redisExe -WindowStyle Hidden
        Start-Sleep 2
        Write-Host "  Redis запущен" -ForegroundColor DarkGreen
    } else {
        Write-Host "  Не удалось запустить Redis. Запустите вручную." -ForegroundColor Red
    }
}

# ——————————————— 6. Фронтенд ———————————————

if (-not $SkipFront) {
    Write-Step "7. Установка фронтенд-зависимостей (npm)"
    Push-Location client-new
    npm install --silent 2>$null
    Pop-Location
    Write-Host "  npm-зависимости установлены" -ForegroundColor DarkGreen
}

# ——————————————— 7. Итог ———————————————

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Установка завершена!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Запуск бэкенда:" -ForegroundColor Cyan
Write-Host "    cd server" -ForegroundColor White
Write-Host "    ..\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -ForegroundColor White
Write-Host ""
Write-Host "  Запуск фронтенда (в другом терминале):" -ForegroundColor Cyan
Write-Host "    cd client-new" -ForegroundColor White
Write-Host "    npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "  Открыть сайт: http://localhost:5173" -ForegroundColor Cyan
Write-Host "  Логин: admin@agile.com / admin123" -ForegroundColor Cyan
Write-Host ""

Wait-ForKey
