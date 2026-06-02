# Техническая документация — Agile Business Platform (Agile.Workspace)

> Репозиторий: [github.com/5eeee/agile-business-platform](https://github.com/5eeee/agile-business-platform)  
> Автор: Владимир Кутомкин

## 1. Назначение

Enterprise-платформа **Agile Business** для управления проектами, командой, обучением и геймификацией: Kanban, итерации, чат, код-редактор, KPI, leaderboard, Telegram-интеграция.

## 2. Стек

| Слой | Технологии |
|------|------------|
| Frontend | React 18, TypeScript, Vite 5, Redux Toolkit, React Router 6, Monaco Editor, Playwright E2E |
| Backend | Python FastAPI 0.115, SQLAlchemy async, Alembic |
| БД | PostgreSQL 16, Redis, Celery |
| Storage | S3/MinIO, Elasticsearch (опц.) |
| Deploy | Docker Compose, GitHub Actions |

## 3. Структура

```
client-new/               # Vite SPA :5173
├── src/pages/            # Projects, Training, Admin, Analytics…
└── package.json

server/
├── app/main.py           # FastAPI :8000
├── app/api/              # auth, projects, tasks, chat, training…
└── requirements.txt

docker-compose.yml, deploy.ps1, start.py
```

## 4. FastAPI API (префикс `/api`)

| Router | Основные endpoints |
|--------|-------------------|
| `/api/auth` | register, login, refresh, me, 2FA |
| `/api/projects` | CRUD, members, archive |
| `/api/iterations` | CRUD, board-columns |
| `/api/tasks` | Kanban, comments, attachments |
| `/api/chat` | messages, polls, upload |
| `/api/training` | courses, code run, submissions |
| `/api/gamification` | coins, shop, leaderboard, KPI |
| `/api/analytics` | dashboard, reports |
| `/api/documents` | versions, upload |
| `/api/telegram` | webhook, link/unlink |
| `/api/health` | healthcheck |

Vite проксирует `/api` и `/ws` → `127.0.0.1:8000`

## 5. Переменные окружения (`server/.env`)

`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `S3_*`, `TELEGRAM_*`, `SMTP_*`, `ADMIN_SEED_EMAIL/PASSWORD`

## 6. Запуск

```powershell
npm run setup
# server/.env + PostgreSQL + Redis
npm start                   # concurrently: Vite + uvicorn
```

Или: `python start.py` / Docker Compose

## 7. Модули платформы

- **Проекты:** итерации, backlog, задачи, ретроспективы
- **Обучение:** курсы, Monaco Editor, квизы, code run
- **Геймификация:** монеты, магазин, KPI, leaderboard
- **Коммуникации:** чат (WebSocket), события, уведомления
- **Документы:** версионирование, upload/download
- **Аналитика:** dashboard, экспорт

## 8. Production

```powershell
npm run deploy              # deploy.ps1 → VPS
docker compose -f docker-compose.prod.yml up -d
```

Alembic migrations, E2E тесты в CI.
