# Запуск Docker + сиды курса и магазина
# Требует: .env в корне с DB_PASSWORD, REDIS_PASSWORD, MINIO_USER, MINIO_PASSWORD, SECRET_KEY

$ErrorActionPreference = "Stop"
$compose = "docker", "compose", "-f", "docker-compose.prod.yml"

Write-Host "`n=== Agile Business: запуск с сидами ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Host "[!] Создайте .env: copy .env.example .env" -ForegroundColor Yellow
    Write-Host "    Заполните: SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD, MINIO_USER, MINIO_PASSWORD, ADMIN_SEED_PASSWORD" -ForegroundColor Gray
    exit 1
}

Write-Host "[1] Сборка и запуск контейнеров..." -ForegroundColor Green
& $compose build
& $compose up -d

Write-Host ""
Write-Host "[2] Ожидание backend (30 сек)..." -ForegroundColor Green
Start-Sleep -Seconds 30

Write-Host ""
Write-Host "[3] Сид курса Fullstack..." -ForegroundColor Green
& $compose run --rm backend python seed_fullstack.py 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (уже загружено или ошибка)" -ForegroundColor Gray }

Write-Host ""
Write-Host "[4] Сид магазина (20 товаров)..." -ForegroundColor Green
& $compose run --rm backend python seed_shop_items.py 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (уже загружено или ошибка)" -ForegroundColor Gray }

Write-Host ""
Write-Host "=== Готово! ===" -ForegroundColor Cyan
Write-Host "Сайт: http://localhost (порт 80)"
Write-Host "Admin: admin@agile.com / пароль из .env (ADMIN_SEED_PASSWORD)"
Write-Host ""
Write-Host "Остановить: docker compose -f docker-compose.prod.yml down" -ForegroundColor Gray
