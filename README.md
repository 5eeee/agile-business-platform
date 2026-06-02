# Agile.Workspace

## Быстрый старт (локально)

1. **Зависимости:** в корне репозитория выполните `npm run setup` (корневой `npm install` + `client-new`).
2. **Бэкенд:** скопируйте `server/.env.example` → `server/.env`, задайте `SECRET_KEY`, при необходимости `DATABASE_URL` и `REDIS_URL`. Нужны запущенные PostgreSQL и Redis (см. `install-local.ps1` или Docker).
3. **Запуск всего сразу:** `npm start` — Vite на [http://localhost:5173](http://localhost:5173), API на `127.0.0.1:8000` (прокси `/api` и `/ws` из Vite).

Проверка API при работающем сервере: `npm run verify`.

### Вход (локально и на сервере)

| Симптом | Частая причина |
|--------|----------------|
| «Сервер недоступен» / `ECONNREFUSED` | API не запущен или упал при старте (часто нет PostgreSQL). См. раздел про Postgres ниже. |
| 403 и текст про CSRF | На сервере `DEBUG=false`: в `server/.env` в `CORS_ORIGINS` должен быть **ровно тот URL**, с которого открыт сайт (схема `https`/`http`, домен, **без** `/` в конце). Добавьте оба варианта, если ходите и по `www`, и без. |
| 401 после перезапуска только что работало | Сменился `SECRET_KEY` или истёк refresh — войдите снова. В **проде** `SECRET_KEY` нельзя менять без сброса сессий. |
| Логин «не тот» пароль | Пароли в БД — не из `.env.example`. После дампа с прода используйте реальные учётки из БД или сброс пароля. |
| После регистрации вход «не пускает» | В проде (`DEBUG=false`) новые пользователи по умолчанию **на модерации** — это нормально. Локально при `DEBUG=true` аккаунт активируется сразу и выполняется авто-вход. Открытая регистрация на проде: `REGISTRATION_AUTO_APPROVE=true` в `server/.env` (повышает риск спама — оставьте rate limit). |

Локально фронт ходит в API через прокси Vite (`/api` → `127.0.0.1:8000`). На сервере — тот же путь `/api` через nginx (см. `client-new/nginx.conf`).

### E2E (Playwright)

Нужны **Vite + API** (`npm start` в корне). Пароль админа из вашей БД (для дампа с прода — не `admin123` из примера, если не совпадает):

```powershell
cd client-new
$env:E2E_ADMIN_EMAIL = "admin@agile.com"
$env:E2E_ADMIN_PASSWORD = "ваш_реальный_пароль"
npm run test:e2e
```

Отчёт: `client-new\playwright-report\index.html`. Интерактивно: `npm run test:e2e:ui`.

**CI:** при push в `main` GitHub Actions (`.github/workflows/deploy.yml`) поднимает PostgreSQL + Redis, выполняет `alembic upgrade head`, стартует API и Vite и гоняет тот же `npm run test:e2e` перед сборкой образов и деплоем.

Альтернатива: `.\dev-up.ps1` (Docker) + отдельно `cd client-new; npm run dev` — см. комментарии в скрипте.

### Если API не стартует

- **`No module named …`** — в каталоге `server` установите зависимости в тот же Python, что подхватывает `scripts/run-server.mjs` (например `.\.venv-1\Scripts\pip install -r requirements.txt`).
- **Битый `.venv`** (часто после удаления Python из Microsoft Store) — удалите папку `.venv` и создайте окружение заново (`install-local.ps1` или `python -m venv .venv` + `pip install -r server/requirements.txt`). Скрипт запуска пропускает неработающие интерпретаторы и берёт следующий кандидат (`.venv-1` и т.д.).

### PostgreSQL (ошибка `init_db`, `asyncpg`, `Connection refused`, Vite: `ECONNREFUSED 127.0.0.1:8000`)

Без работающего Postgres процесс API завершается — порт **8000** не слушается, фронт не может проксировать `/api`.

**Вариант A — Docker (быстро, совпадает с `server/.env.example`):**

```powershell
docker run -d --name agile-pg -p 5432:5432 -e POSTGRES_USER=agile -e POSTGRES_PASSWORD=agile_pass -e POSTGRES_DB=agile_db postgres:16-alpine
```

В `server/.env` должно быть:  
`DATABASE_URL=postgresql+asyncpg://agile:agile_pass@localhost:5432/agile_db`

**Вариант B — установленный PostgreSQL:** создайте пользователя, БД и выставьте тот же формат строки в `server/.env` (см. `install-local.ps1`).

### Redis

Если в логе `Rate limiter: Redis недоступен` — лимиты работают в памяти процесса; для полного поведения поднимите Redis и проверьте `REDIS_URL` в `server/.env`.

### Дамп БД с VPS по SSH (на своём ПК)

Среда Cursor не имеет доступа к вашим SSH-ключам — дамп делаете вы локально. Скрипт: `scripts/remote-db-dump.ps1` (PostgreSQL в Docker на сервере, как в `docker-compose.yml`).

```powershell
cd D:\agile_workspace
$env:REMOTE_PG_PASSWORD = 'значение DB_PASSWORD с сервера'
.\scripts\remote-db-dump.ps1 -SshTarget user@ваш-сервер -RemoteRepoPath /путь/к/репозиторию/на/vps
# при необходимости: -IdentityFile ~\.ssh\id_ed25519
```

Файл появится в `backups\remote_YYYYMMDD_HHMMSS.sql`. Папка `backups/*.sql` в `.gitignore`, в git дампы не попадут.
