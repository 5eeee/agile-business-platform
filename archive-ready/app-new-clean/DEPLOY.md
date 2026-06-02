# Деплой Agile Business на VPS

## Архитектура

- **VPS** — PostgreSQL, Redis, MinIO, FastAPI backend, React frontend (Docker)
- **Домен** — app.agile-business-pro.com → A-запись на IP VPS
- **Бэкапы** — автоматически ежедневно в 03:00

## Шаг 1: Подготовка .env

```bash
# В корне проекта
cp .env.production.example .env

# Добавьте в .env:
VPS_HOST=IP_ВАШЕГО_VPS        # например 89.104.67.148
VPS_USER=root
VPS_PASSWORD=пароль_root      # для автоматического деплоя
DEPLOY_DOMAIN=app.agile-business-pro.com
```

## Шаг 2: Деплой

```bash
pip install paramiko
python deploy_vps.py
```

При деплое автоматически выполняются сиды:
- **seed_fullstack.py** — курс Fullstack Web-Developer (4 блока)
- **seed_shop_items.py** — 20 товаров магазина (статусы, бейджи, перки)

Или через PowerShell (потребует ввод пароля при `scp`/`ssh`):

```powershell
powershell -ExecutionPolicy Bypass -File deploy.ps1 -Server 89.104.67.148 -Domain app.agile-business-pro.com
```

## Шаг 3: DNS

Создайте A-запись для поддомена:
- **app.agile-business-pro.com** → IP вашего VPS

## Бэкапы БД

- **Создать:** `./db-backup.sh` (на VPS в `/opt/agile/`)
- **Список:** `./db-backup.sh --list`
- **Восстановить:** `./db-backup.sh --restore agile_workspace_YYYYMMDD_HHMMSS.sql.gz`
- **Cron:** автоматически в 03:00

## Безопасность

- Пароли и ключи — только в `.env` (в .gitignore)
- Никогда не коммитьте `.env`, `.env.deploy`, `*.pem`
- После деплоя смените ADMIN_SEED_PASSWORD
