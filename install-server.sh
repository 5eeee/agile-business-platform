#!/usr/bin/env bash
# ============================================================
# Agile Business — Установка на Ubuntu сервер (Docker)
# Запуск: chmod +x install-server.sh && sudo ./install-server.sh
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

step() { echo -e "\n${GREEN}>> $1${NC}"; }
warn() { echo -e "${YELLOW}   $1${NC}"; }
fail() { echo -e "${RED}   ОШИБКА: $1${NC}"; exit 1; }
ok()   { echo -e "${GREEN}   [OK] $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Agile Business — Установка (Ubuntu)${NC}"
echo -e "${CYAN}========================================${NC}"

# ——————————————— 0. Проверка root ———————————————

if [ "$EUID" -ne 0 ]; then
    fail "Запустите скрипт с sudo: sudo ./install-server.sh"
fi

# ——————————————— 1. Обновление системы ———————————————

step "1. Обновление пакетов"
apt-get update -qq
apt-get upgrade -y -qq
ok "Система обновлена"

# ——————————————— 2. Docker ———————————————

step "2. Установка Docker"
if command -v docker &>/dev/null; then
    ok "Docker уже установлен: $(docker --version)"
else
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    ok "Docker установлен: $(docker --version)"
fi

# ——————————————— 3. Docker Compose ———————————————

step "3. Проверка Docker Compose"
if docker compose version &>/dev/null; then
    ok "Docker Compose: $(docker compose version --short)"
else
    fail "Docker Compose plugin не установлен"
fi

# ——————————————— 4. Firewall ———————————————

step "4. Настройка файрвола (ufw)"
if command -v ufw &>/dev/null; then
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw --force enable
    ok "Открыты порты: 22, 80, 443"
else
    warn "ufw не найден, пропускаем"
fi

# ——————————————— 5. Конфигурация .env ———————————————

step "5. Создание .env файла"

generate_password() {
    openssl rand -base64 24 | tr -d '/+=' | cut -c1-24
}

if [ ! -f .env ]; then
    DB_PASSWORD=$(generate_password)
    REDIS_PASSWORD=$(generate_password)
    MINIO_PASSWORD=$(generate_password)
    SECRET_KEY=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-48)

    cat > .env <<ENVFILE
# ===== Agile Business — Production =====
# Сгенерировано автоматически: $(date -Iseconds)

# --- Приложение ---
DEBUG=false
SECRET_KEY=${SECRET_KEY}
DOMAIN=\${DOMAIN:-localhost}

# --- PostgreSQL ---
DB_USER=agile_user
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=agile_db
DATABASE_URL=postgresql+asyncpg://agile_user:${DB_PASSWORD}@db:5432/agile_db

# --- Redis ---
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# --- Elasticsearch ---
ELASTIC_PASSWORD=$(generate_password)

# --- MinIO (S3) ---
MINIO_USER=agile-minio
MINIO_PASSWORD=${MINIO_PASSWORD}
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=agile-minio
S3_SECRET_KEY=${MINIO_PASSWORD}
S3_BUCKET=agile-files

# --- Порты ---
FRONTEND_PORT=80
BACKEND_PORT=8000

# --- Uvicorn ---
WORKERS=2

# --- Admin seed ---
ADMIN_SEED_EMAIL=admin@agile.com
ADMIN_SEED_PASSWORD=$(generate_password)

# --- CORS (JSON массив) ---
CORS_ORIGINS=["https://\${DOMAIN:-localhost}"]

# --- Telegram (опционально) ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
TELEGRAM_WEBHOOK_SECRET=
ENVFILE

    chmod 600 .env
    ok "Создан .env с безопасными паролями"
    echo ""
    warn "ВАЖНО! Сохраните пароли:"
    echo -e "   DB_PASSWORD:    ${DB_PASSWORD}"
    echo -e "   REDIS_PASSWORD: ${REDIS_PASSWORD}"
    echo -e "   MINIO_PASSWORD: ${MINIO_PASSWORD}"
    echo ""
    warn "Отредактируйте .env — укажите DOMAIN и Telegram-токен"
else
    ok ".env уже существует — пропускаем"
fi

# ——————————————— 6. Создаём папку для бэкапов ———————————————

step "6. Создание папки для бэкапов"
mkdir -p backups
chmod 700 backups
ok "Папка backups/ создана"

# ——————————————— 7. Сборка и запуск ———————————————

step "7. Сборка и запуск Docker-контейнеров"

# Загружаем переменные для подстановки
set -a
source .env
set +a

docker compose build --quiet
docker compose up -d

echo ""
step "Ожидание готовности сервисов (до 60 сек)..."
for i in $(seq 1 30); do
    if docker compose exec -T backend curl -sf http://localhost:8000/api/health &>/dev/null; then
        ok "Backend готов"
        break
    fi
    if [ "$i" -eq 30 ]; then
        warn "Backend ещё не готов — проверьте логи: docker compose logs backend"
    fi
    sleep 2
done

# ——————————————— 8. Cron для бэкапов ———————————————

step "8. Настройка автобэкапа (cron)"

BACKUP_SCRIPT="$SCRIPT_DIR/db-backup.sh"
if [ -f "$BACKUP_SCRIPT" ]; then
    chmod +x "$BACKUP_SCRIPT"
    CRON_LINE="0 3 * * * $BACKUP_SCRIPT >> $SCRIPT_DIR/backups/cron.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "db-backup.sh"; echo "$CRON_LINE") | crontab -
    ok "Бэкап БД каждый день в 03:00"
else
    warn "db-backup.sh не найден — автобэкап не настроен"
fi

# ——————————————— Итог ———————————————

DOMAIN_VAL=${DOMAIN:-localhost}
ADMIN_PASS=$(grep ADMIN_SEED_PASSWORD .env | cut -d= -f2)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Установка завершена!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Сайт:    ${CYAN}http://${DOMAIN_VAL}${NC}"
echo -e "  Логин:   ${CYAN}$(grep ADMIN_SEED_EMAIL .env | cut -d= -f2)${NC}"
echo -e "  Пароль:  ${CYAN}${ADMIN_PASS}${NC}"
echo ""
echo -e "  ${YELLOW}Полезные команды:${NC}"
echo -e "    docker compose logs -f          — логи всех сервисов"
echo -e "    docker compose restart backend  — перезапуск бэкенда"
echo -e "    ./db-backup.sh                  — создать бэкап БД"
echo -e "    ./db-backup.sh --restore FILE   — восстановить из бэкапа"
echo ""
