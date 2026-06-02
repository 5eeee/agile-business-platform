# Локальная разработка: Docker (API, БД, Redis, MinIO) + порт 8000 на хосте для Vite.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Write-Host "Создайте .env: copy .env.example .env" -ForegroundColor Yellow
    exit 1
}

Write-Host "Запуск docker-compose.prod.yml..." -ForegroundColor Cyan
docker compose -f docker-compose.prod.yml up -d --remove-orphans

Write-Host ""
Write-Host "Готово." -ForegroundColor Green
Write-Host "  API (для Vite):  http://127.0.0.1:8000/docs"
Write-Host "  Сборка в Docker: http://localhost:<FRONTEND_PORT> (в .env, например 3000)"
Write-Host "  Vite (отдельно):  cd client-new; npm run dev  -> http://localhost:5173"
Write-Host ""
Write-Host "Админ: email из ADMIN_SEED_EMAIL, пароль из ADMIN_SEED_PASSWORD в .env" -ForegroundColor Gray
