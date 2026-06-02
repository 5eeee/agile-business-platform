#!/usr/bin/env bash
# ============================================================
# Agile Business — Утилита бэкапа и восстановления БД
#
# Использование:
#   ./db-backup.sh                     — создать бэкап
#   ./db-backup.sh --restore FILE      — восстановить из файла
#   ./db-backup.sh --list              — список бэкапов
#   ./db-backup.sh --clean [DAYS]      — удалить бэкапы старше N дней (по умолчанию 30)
#
# Поддерживает:
#   - Docker (через docker compose exec)
#   - Локальный PostgreSQL (через pg_dump / psql напрямую)
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
mkdir -p "$BACKUP_DIR"

# ——— Определяем режим (Docker или локальный) ———

USE_DOCKER=false
if command -v docker &>/dev/null && docker compose ps db 2>/dev/null | grep -q "running"; then
    USE_DOCKER=true
fi

# ——— Загружаем .env ———

load_env() {
    local env_file=""
    if [ -f "$SCRIPT_DIR/.env" ]; then
        env_file="$SCRIPT_DIR/.env"
    elif [ -f "$SCRIPT_DIR/server/.env" ]; then
        env_file="$SCRIPT_DIR/server/.env"
    fi

    if [ -n "$env_file" ]; then
        set -a
        source "$env_file"
        set +a
    fi

    DB_USER="${DB_USER:-agile_user}"
    DB_NAME="${DB_NAME:-agile_workspace}"
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
}

load_env

# ——— Функции ———

do_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local filename="agile_workspace_${timestamp}.sql.gz"
    local filepath="${BACKUP_DIR}/${filename}"

    echo -e "${CYAN}Создание бэкапа...${NC}"

    if $USE_DOCKER; then
        docker compose exec -T -e PGPASSWORD="$DB_PASSWORD" db pg_dump \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists \
            | gzip > "$filepath"
    else
        PGPASSWORD="${DB_PASSWORD}" pg_dump \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists \
            | gzip > "$filepath"
    fi

    local size=$(du -h "$filepath" | cut -f1)
    echo -e "${GREEN}[OK] Бэкап создан: ${filename} (${size})${NC}"
    echo "$filepath"
}

do_restore() {
    local filepath="$1"

    # Поддержка имени файла без полного пути
    if [ ! -f "$filepath" ]; then
        if [ -f "${BACKUP_DIR}/${filepath}" ]; then
            filepath="${BACKUP_DIR}/${filepath}"
        else
            echo -e "${RED}Файл не найден: ${filepath}${NC}"
            exit 1
        fi
    fi

    echo -e "${YELLOW}ВНИМАНИЕ: Восстановление из бэкапа перезапишет текущую БД!${NC}"
    echo -e "Файл: ${CYAN}$(basename "$filepath")${NC}"
    read -p "Продолжить? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Отменено."
        exit 0
    fi

    echo -e "${CYAN}Восстановление БД...${NC}"

    if $USE_DOCKER; then
        gunzip -c "$filepath" | docker compose exec -T -e PGPASSWORD="$DB_PASSWORD" -i db psql \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --quiet \
            2>/dev/null
    else
        gunzip -c "$filepath" | PGPASSWORD="${DB_PASSWORD}" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --quiet \
            2>/dev/null
    fi

    echo -e "${GREEN}[OK] БД восстановлена из $(basename "$filepath")${NC}"
    echo ""
    echo -e "${YELLOW}Рекомендуется перезапустить бэкенд:${NC}"
    if $USE_DOCKER; then
        echo "  docker compose restart backend"
    else
        echo "  Перезапустите uvicorn вручную"
    fi
}

do_list() {
    echo -e "${CYAN}Список бэкапов:${NC}"
    echo ""

    local count=0
    for f in "$BACKUP_DIR"/agile_workspace_*.sql.gz; do
        [ -f "$f" ] || continue
        count=$((count + 1))
        local name=$(basename "$f")
        local size=$(du -h "$f" | cut -f1)
        local date_part=$(echo "$name" | sed 's/agile_workspace_\([0-9]\{8\}\)_\([0-9]\{6\}\).*/\1 \2/')
        local formatted=$(echo "$date_part" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\) \([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:\6/')
        echo -e "  ${GREEN}${name}${NC}  (${size})  ${formatted}"
    done

    if [ "$count" -eq 0 ]; then
        echo -e "  ${YELLOW}Бэкапов нет${NC}"
    else
        echo ""
        echo "  Всего: ${count}"
    fi
}

do_clean() {
    local days="${1:-30}"
    echo -e "${CYAN}Удаление бэкапов старше ${days} дней...${NC}"

    local count=0
    find "$BACKUP_DIR" -name "agile_workspace_*.sql.gz" -mtime "+${days}" -print0 | while IFS= read -r -d '' f; do
        rm "$f"
        echo -e "  Удалён: $(basename "$f")"
        count=$((count + 1))
    done

    echo -e "${GREEN}Готово${NC}"
}

show_help() {
    echo "Agile Business — Утилита бэкапа БД"
    echo ""
    echo "Использование:"
    echo "  $0                      Создать бэкап"
    echo "  $0 --restore ФАЙЛ      Восстановить из файла"
    echo "  $0 --list               Список бэкапов"
    echo "  $0 --clean [ДНЕЙ]       Удалить старые бэкапы (по умолчанию 30 дней)"
    echo "  $0 --help               Эта справка"
    echo ""
    echo "Режим: $(if $USE_DOCKER; then echo 'Docker'; else echo 'Локальный PostgreSQL'; fi)"
}

# ——— Точка входа ———

case "${1:-}" in
    --restore)
        [ -z "${2:-}" ] && { echo -e "${RED}Укажите файл: $0 --restore ФАЙЛ${NC}"; exit 1; }
        do_restore "$2"
        ;;
    --list)
        do_list
        ;;
    --clean)
        do_clean "${2:-30}"
        ;;
    --help|-h)
        show_help
        ;;
    "")
        do_backup
        ;;
    *)
        echo -e "${RED}Неизвестная команда: $1${NC}"
        show_help
        exit 1
        ;;
esac
