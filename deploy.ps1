# ============================================================
# Agile Business — Загрузка и развёртывание на VPS
# Запуск: powershell -ExecutionPolicy Bypass -File deploy.ps1
# ============================================================

param(
    [string]$Server = "89.104.67.148",
    [string]$Domain = "app.agile-business-pro.com",
    [string]$User = "root",
    [int]$Port = 22,
    [string]$RemotePath = "/opt/agile",
    [switch]$SkipUpload  # Пропустить загрузку файлов (если уже загружены)
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Agile Business — Деплой на VPS"       -ForegroundColor Cyan
Write-Host "  Сервер: $User@$Server"                -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ——— Проверяем SSH ———

if (-not (Get-Command "ssh" -ErrorAction SilentlyContinue)) {
    Write-Host "SSH не найден. Установите OpenSSH Client:" -ForegroundColor Red
    Write-Host "  Параметры → Приложения → Дополнительные компоненты → OpenSSH Client" -ForegroundColor Yellow
    exit 1
}

# ——— 1. Загрузка файлов ———

if (-not $SkipUpload) {
    Write-Host ">> 1. Загрузка проекта на сервер..." -ForegroundColor Green
    Write-Host "   (Может запросить пароль от сервера)" -ForegroundColor Yellow

    # Создаём директорию
    ssh -p $Port "${User}@${Server}" "mkdir -p $RemotePath"

    # Список файлов и папок для загрузки
    $items = @(
        "server",
        "client-new",
        "docker-compose.prod.yml",
        "db-backup.sh",
        ".env.example"
    )

    foreach ($item in $items) {
        $localPath = Join-Path $ROOT $item
        if (-not (Test-Path $localPath)) {
            Write-Host "   ПРОПУСК: $item не найден" -ForegroundColor Yellow
            continue
        }

        Write-Host "   Копирую: $item" -ForegroundColor DarkGreen
        scp -r -P $Port "$localPath" "${User}@${Server}:${RemotePath}/"
    }

    Write-Host "   [OK] Файлы загружены" -ForegroundColor Green
}

# ——— 2. Удалённая установка ———

Write-Host ""
Write-Host ">> 2. Настройка сервера..." -ForegroundColor Green

# Генерируем пароли локально
$DB_PASSWORD = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
$REDIS_PASSWORD = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
$MINIO_PASSWORD = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
$SECRET_KEY = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
$ADMIN_PASSWORD = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object {[char]$_})

# Команды для выполнения на сервере
$setupScript = @"
set -e

cd $RemotePath

# Переименовываем docker-compose
cp docker-compose.prod.yml docker-compose.yml

# Создаём .env если нет
if [ ! -f .env ]; then
cat > .env << 'ENVEOF'
DEBUG=false
SECRET_KEY=$SECRET_KEY
DOMAIN=$Domain
DB_PASSWORD=$DB_PASSWORD
REDIS_PASSWORD=$REDIS_PASSWORD
MINIO_USER=agile-minio
MINIO_PASSWORD=$MINIO_PASSWORD
FRONTEND_PORT=80
ADMIN_SEED_EMAIL=admin@agile.com
ADMIN_SEED_PASSWORD=$ADMIN_PASSWORD
CORS_ORIGINS=["https://$Domain","http://$Domain","https://$Server","http://$Server"]
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
ENVEOF
chmod 600 .env
echo '[OK] .env создан'
else
echo '[OK] .env уже существует'
fi

# Swap (если нет)
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo '[OK] Swap 2GB создан'
fi

# Папка для бэкапов
mkdir -p backups
chmod +x db-backup.sh 2>/dev/null || true

# Firewall
if command -v ufw &>/dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    echo '[OK] Firewall настроен'
fi

# Собираем и запускаем
echo 'Сборка контейнеров (это может занять несколько минут)...'
docker compose build
docker compose up -d

echo ''
echo 'Ожидание готовности...'
for i in \$(seq 1 40); do
    if docker compose exec -T backend curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo '[OK] Backend работает!'
        break
    fi
    if [ "\$i" -eq 40 ]; then
        echo 'Backend ещё запускается. Проверьте: docker compose logs backend'
    fi
    sleep 3
done

# Cron для бэкапов
if [ -f db-backup.sh ]; then
    CRON_LINE="0 3 * * * $RemotePath/db-backup.sh >> $RemotePath/backups/cron.log 2>&1"
    (crontab -l 2>/dev/null | grep -v 'db-backup.sh'; echo "\$CRON_LINE") | crontab -
    echo '[OK] Автобэкап в 03:00'
fi

echo ''
echo '================================='
echo '  УСТАНОВКА ЗАВЕРШЕНА!'
echo '================================='
echo "  Сайт: https://$Domain (или http://$Server)"
echo "  Логин: admin@agile.com"
echo "  Пароль: $ADMIN_PASSWORD"
echo ''
echo '  Сохраните пароли!'
echo "  DB:    $DB_PASSWORD"
echo "  Redis: $REDIS_PASSWORD"
echo "  MinIO: $MINIO_PASSWORD"
echo '================================='
"@

ssh -p $Port "${User}@${Server}" $setupScript

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Деплой завершён!" -ForegroundColor Green
Write-Host "  Сайт: http://$Server" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Нажмите любую клавишу..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
