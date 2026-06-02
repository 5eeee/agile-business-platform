"""
Скрипт заполнения курсов обучения из структуры компетенций.
Запуск внутри контейнера backend:
  docker compose exec backend python seed_courses.py
"""
import asyncio
import uuid
from sqlalchemy import select
from app.database import engine, async_session
from app.models.user import User, UserRole
from app.models.training import (
    TrainingCourse, TrainingTopic, TrainingContent, TrainingTask,
)

# ===================== ДАННЫЕ КУРСОВ =====================
# Структура: сферы → направления → темы (из competency.html)

SPHERES = [
    {
        "name": "Информационные технологии (IT)",
        "directions": [
            {
                "name": "Frontend-разработка",
                "desc": "Разработка пользовательских интерфейсов: HTML, CSS, JavaScript, фреймворки",
                "topics": [
                    {"name": "HTML: теги, семантика, формы", "level": "basic", "order": 1,
                     "content": "Основы HTML5: структурные теги (header, main, footer, section, article), семантическая разметка, формы и валидация, таблицы, мультимедиа-элементы.",
                     "task": "Создайте HTML-страницу с формой регистрации, используя семантические теги. Форма должна содержать: имя, email, пароль, выбор роли (select), чекбокс согласия и кнопку отправки."},
                    {"name": "CSS: селекторы, блочная модель, позиционирование", "level": "basic", "order": 2,
                     "content": "Селекторы CSS (классы, id, псевдоклассы, комбинаторы), блочная модель (margin, padding, border), позиционирование (static, relative, absolute, fixed, sticky), единицы измерения.",
                     "task": "Сверстайте карточку товара с изображением, заголовком, описанием и ценой. Используйте позиционирование для бейджа «Новинка» в углу карточки."},
                    {"name": "CSS: Flexbox, Grid, адаптивная вёрстка", "level": "medium", "order": 3,
                     "content": "Flexbox: оси, выравнивание, flex-grow/shrink/basis. CSS Grid: строки и колонки, grid-template-areas, auto-fill/auto-fit. Media queries, mobile-first подход.",
                     "task": "Создайте адаптивную сетку карточек: 3 колонки на десктопе, 2 на планшете, 1 на мобильном. Используйте CSS Grid и media queries."},
                    {"name": "JavaScript: синтаксис, типы данных, операторы", "level": "basic", "order": 4,
                     "content": "Переменные (let, const, var), типы данных (string, number, boolean, null, undefined, object, symbol), операторы, условия (if/else, switch), циклы (for, while, for...of).",
                     "task": "Напишите функцию, которая принимает массив чисел и возвращает объект с полями: sum, avg, min, max."},
                    {"name": "JavaScript: DOM, события, обработчики", "level": "medium", "order": 5,
                     "content": "DOM API: querySelector, createElement, appendChild, innerHTML. События: addEventListener, всплытие и перехват, делегирование событий. Работа с формами.",
                     "task": "Создайте интерактивный список задач (todo-list): добавление, удаление, отметка выполненных. Используйте делегирование событий."},
                    {"name": "JavaScript: async/await, промисы, замыкания", "level": "advanced", "order": 6,
                     "content": "Промисы: создание, цепочки (.then/.catch), Promise.all/race/allSettled. Async/await синтаксис. Замыкания и лексическое окружение. Event Loop.",
                     "task": "Напишите функцию, которая параллельно запрашивает данные с 3 API-эндпоинтов и возвращает объединённый результат. Обработайте ошибки gracefully."},
                    {"name": "JavaScript: ES6+ (деструктуризация, модули, spread)", "level": "medium", "order": 7,
                     "content": "Деструктуризация массивов и объектов, spread/rest операторы, шаблонные строки, стрелочные функции, Map/Set, Symbol, итераторы, модули (import/export).",
                     "task": "Перепишите набор функций с ES5 на ES6+: используйте деструктуризацию, spread, стрелочные функции и модульную структуру."},
                    {"name": "Фреймворки: React / Vue / Angular (основы)", "level": "advanced", "order": 8,
                     "content": "Компонентный подход, виртуальный DOM, однонаправленный поток данных. React: JSX, хуки (useState, useEffect), props. Vue: реактивность, директивы. Angular: модули, сервисы, DI.",
                     "task": "Создайте простое SPA-приложение на React: список пользователей с поиском и фильтрацией. Используйте хуки useState и useEffect для состояния и API-запросов."},
                    {"name": "Сборка: Webpack, Vite, npm/yarn", "level": "medium", "order": 9,
                     "content": "Package managers: npm, yarn, pnpm. Бандлеры: Webpack (loaders, plugins), Vite (ESM, HMR). Конфигурация: babel, PostCSS, TypeScript. Скрипты в package.json.",
                     "task": "Настройте проект с Vite: TypeScript, CSS Modules, алиасы путей. Добавьте скрипты для dev, build и preview."},
                    {"name": "Тестирование: Jest, Cypress, E2E", "level": "advanced", "order": 10,
                     "content": "Виды тестов: unit, integration, E2E. Jest: describe/it/expect, моки, снепшоты. React Testing Library. Cypress: селекторы, команды, фикстуры.",
                     "task": "Напишите unit-тесты для 3 утилитарных функций и E2E тест для формы регистрации с помощью Cypress."},
                ],
            },
            {
                "name": "Backend-разработка",
                "desc": "Серверная разработка: API, аутентификация, архитектура, кэширование",
                "topics": [
                    {"name": "HTTP: методы, статус-коды, заголовки", "level": "basic", "order": 1,
                     "content": "Протокол HTTP/HTTPS. Методы: GET, POST, PUT, PATCH, DELETE. Статус-коды: 2xx, 3xx, 4xx, 5xx. Заголовки: Content-Type, Authorization, Cache-Control, CORS.",
                     "task": "Опишите, какие HTTP-методы и статус-коды вы бы использовали для CRUD-операций API управления задачами. Объясните выбор заголовков."},
                    {"name": "REST API: принципы, проектирование эндпоинтов", "level": "basic", "order": 2,
                     "content": "Принципы REST: ресурсы, HTTP-глаголы, статус-коды, HATEOAS. Версионирование API. Пагинация, фильтрация, сортировка. OpenAPI/Swagger документация.",
                     "task": "Спроектируйте REST API для системы управления проектами: ресурсы (projects, tasks, users), эндпоинты, параметры, примеры ответов."},
                    {"name": "Аутентификация: JWT, OAuth, сессии", "level": "medium", "order": 3,
                     "content": "Аутентификация vs авторизация. JWT: структура, подпись, refresh tokens. OAuth 2.0: grant types, потоки. Сессии: cookie-based, хранилище. Безопасность: CSRF, XSS.",
                     "task": "Реализуйте JWT-аутентификацию: эндпоинты login, refresh, logout. Объясните, как хранить токены на клиенте и защитить от XSS/CSRF."},
                    {"name": "Серверный язык: Node.js / Python / PHP / Go", "level": "basic", "order": 4,
                     "content": "Выбор серверного языка: Node.js (Express, Fastify), Python (FastAPI, Django), PHP (Laravel), Go (Gin). Асинхронность, многопоточность, экосистема.",
                     "task": "Создайте простой REST API на выбранном языке/фреймворке с CRUD для сущности «Задача» (title, description, status, priority)."},
                    {"name": "ORM: Sequelize, SQLAlchemy, Eloquent", "level": "medium", "order": 5,
                     "content": "ORM: маппинг объектов на таблицы, миграции, связи (1:1, 1:N, N:M). Sequelize (Node.js), SQLAlchemy (Python), Eloquent (PHP). Проблема N+1, eager/lazy loading.",
                     "task": "Создайте модели «Проект» и «Задача» с связью один-ко-многим. Напишите запрос, который получает проект со всеми задачами, избегая проблемы N+1."},
                    {"name": "Middleware и обработка ошибок", "level": "medium", "order": 6,
                     "content": "Middleware: концепция, порядок выполнения. Логирование, аутентификация, rate limiting, CORS. Централизованная обработка ошибок, custom exceptions, error responses.",
                     "task": "Напишите middleware для: 1) логирования запросов, 2) проверки JWT, 3) rate limiting (макс. 100 запросов/мин). Добавьте обработчик ошибок."},
                    {"name": "Принципы SOLID и паттерны проектирования", "level": "advanced", "order": 7,
                     "content": "SOLID: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. Паттерны: Repository, Factory, Observer, Strategy, Decorator.",
                     "task": "Перепишите монолитный сервис (500+ строк) с применением SOLID. Выделите репозитории, сервисы и используйте Dependency Injection."},
                    {"name": "Микросервисная архитектура", "level": "advanced", "order": 8,
                     "content": "Монолит vs микросервисы. Decomposition patterns. Inter-service communication: REST, gRPC, событийная модель. API Gateway. Service discovery. Saga pattern.",
                     "task": "Спроектируйте декомпозицию монолитного приложения на микросервисы. Определите границы сервисов, способы коммуникации и обработку distributed transactions."},
                    {"name": "Message Queue: RabbitMQ, Kafka", "level": "advanced", "order": 9,
                     "content": "Асинхронная коммуникация. RabbitMQ: exchange, queue, routing. Apache Kafka: topics, partitions, consumer groups. Паттерны: pub/sub, work queue, dead letter queue.",
                     "task": "Реализуйте систему уведомлений с очередью сообщений: отправка email/push при создании задачи. Опишите обработку ошибок и retry-логику."},
                    {"name": "Кэширование: Redis, Memcached, HTTP-кэш", "level": "advanced", "order": 10,
                     "content": "Стратегии кэширования: cache-aside, write-through, write-behind. Redis: строки, хеши, списки, TTL, pub/sub. HTTP кэширование: ETag, Cache-Control. CDN.",
                     "task": "Добавьте кэширование Redis в API: кэш списка проектов, инвалидация при обновлении. Замерьте разницу в скорости с кэшем и без."},
                ],
            },
            {
                "name": "DevOps и инфраструктура",
                "desc": "Git, Docker, CI/CD, Kubernetes, мониторинг, облака",
                "topics": [
                    {"name": "Git: ветвление, merge, rebase, конфликты", "level": "basic", "order": 1,
                     "content": "Git: init, clone, add, commit, push, pull. Ветвление: feature branches, Git Flow, trunk-based. Merge vs rebase. Разрешение конфликтов. .gitignore, hooks.",
                     "task": "Создайте репозиторий с Git Flow: main, develop, feature/*, release/*. Выполните merge с конфликтом и разрешите его. Опишите стратегию ветвления."},
                    {"name": "Linux: командная строка, файловая система, права", "level": "basic", "order": 2,
                     "content": "Командная строка: ls, cd, cp, mv, rm, find, grep, awk, sed. Файловая система: /, /home, /etc, /var. Права: chmod, chown, umask. Процессы: ps, top, kill. SSH.",
                     "task": "Напишите bash-скрипт, который: 1) находит все .log файлы старше 7 дней, 2) архивирует их в tar.gz, 3) удаляет оригиналы. Добавьте запуск по cron."},
                    {"name": "Docker: образы, контейнеры, Dockerfile", "level": "medium", "order": 3,
                     "content": "Docker: контейнеризация vs виртуализация. Dockerfile: FROM, RUN, COPY, EXPOSE, CMD. Образы: слои, кэш, multi-stage builds. Volumes, networks. Docker Hub.",
                     "task": "Напишите Dockerfile для Python/Node.js приложения с multi-stage build. Оптимизируйте размер образа, используйте .dockerignore."},
                    {"name": "Docker Compose: мульти-контейнерное окружение", "level": "medium", "order": 4,
                     "content": "docker-compose.yml: services, networks, volumes. Зависимости (depends_on), переменные окружения, healthchecks. Override файлы для dev/prod.",
                     "task": "Создайте docker-compose.yml для стека: app + PostgreSQL + Redis + nginx. Настройте healthchecks, volumes для данных, .env файл."},
                    {"name": "CI/CD: GitHub Actions, GitLab CI, Jenkins", "level": "medium", "order": 5,
                     "content": "CI/CD пайплайн: build, test, deploy. GitHub Actions: workflows, jobs, steps, secrets. GitLab CI: .gitlab-ci.yml, stages, runners. Артефакты, кэширование.",
                     "task": "Настройте CI/CD пайплайн: lint → test → build Docker image → deploy to staging. Используйте GitHub Actions или GitLab CI."},
                    {"name": "Kubernetes: поды, сервисы, деплойменты", "level": "advanced", "order": 6,
                     "content": "Kubernetes: архитектура, kubectl. Pod, Deployment, Service, Ingress. ConfigMap, Secret. Namespace. Rolling updates, rollback. Liveness/readiness probes.",
                     "task": "Разверните приложение в Kubernetes: Deployment (3 реплики), Service (ClusterIP), Ingress. Настройте ConfigMap для конфигурации."},
                    {"name": "IaC: Terraform, Ansible", "level": "advanced", "order": 7,
                     "content": "Infrastructure as Code: декларативный vs императивный подход. Terraform: провайдеры, ресурсы, модули, state. Ansible: playbooks, roles, inventory.",
                     "task": "Напишите Terraform конфигурацию для создания VPS, настройки firewall и DNS. Или Ansible playbook для настройки сервера с Docker."},
                    {"name": "Мониторинг: Prometheus, Grafana, ELK", "level": "advanced", "order": 8,
                     "content": "Мониторинг: метрики, логи, трейсы. Prometheus: scraping, PromQL, alerting. Grafana: дашборды, панели. ELK Stack: Elasticsearch, Logstash, Kibana. Alertmanager.",
                     "task": "Настройте мониторинг для приложения: Prometheus метрики (HTTP latency, error rate), Grafana дашборд, алерт при error rate > 5%."},
                    {"name": "Облака: AWS / GCP / Azure (основы)", "level": "medium", "order": 9,
                     "content": "Облачные провайдеры: IaaS, PaaS, SaaS. AWS: EC2, S3, RDS, Lambda, ECS. GCP: Compute Engine, Cloud Storage, Cloud Run. Azure: VM, Blob Storage, App Service.",
                     "task": "Разверните приложение в облаке: VPS (EC2/Compute Engine), база данных (RDS), файлы (S3). Опишите архитектуру и стоимость."},
                    {"name": "Сети: DNS, HTTPS, reverse proxy, load balancer", "level": "medium", "order": 10,
                     "content": "DNS: A, CNAME, MX, TXT записи. HTTPS: TLS/SSL, Let's Encrypt, сертификаты. Reverse proxy: nginx, Traefik. Load balancing: round-robin, least connections.",
                     "task": "Настройте nginx как reverse proxy с HTTPS (Let's Encrypt). Добавьте rate limiting, gzip compression и кэширование статики."},
                ],
            },
            {
                "name": "Базы данных",
                "desc": "SQL, проектирование, оптимизация, NoSQL, безопасность",
                "topics": [
                    {"name": "SQL: SELECT, JOIN, WHERE, GROUP BY", "level": "basic", "order": 1,
                     "content": "SQL: SELECT, FROM, WHERE, ORDER BY, LIMIT. JOINs: INNER, LEFT, RIGHT, FULL OUTER, CROSS. Агрегация: COUNT, SUM, AVG, MIN, MAX, GROUP BY, HAVING.",
                     "task": "Напишите SQL-запросы для базы интернет-магазина: 1) топ-5 товаров по продажам, 2) средний чек по месяцам, 3) клиенты без заказов."},
                    {"name": "SQL: подзапросы, оконные функции, CTE", "level": "medium", "order": 2,
                     "content": "Подзапросы: скалярные, IN, EXISTS, коррелированные. CTE (WITH): рекурсивные CTE. Оконные функции: ROW_NUMBER, RANK, LAG, LEAD, SUM OVER, PARTITION BY.",
                     "task": "Напишите запросы с оконными функциями: 1) ранжирование сотрудников по зарплате в отделе, 2) нарастающий итог продаж, 3) разница с предыдущим периодом."},
                    {"name": "Проектирование: нормализация, ER-диаграммы", "level": "medium", "order": 3,
                     "content": "Нормальные формы: 1NF, 2NF, 3NF, BCNF. Денормализация. ER-диаграммы: сущности, атрибуты, связи. Проектирование схемы: именование, типы данных, ограничения.",
                     "task": "Спроектируйте базу данных для системы обучения: курсы, уроки, пользователи, прохождение. Нарисуйте ER-диаграмму и напишите DDL-скрипт."},
                    {"name": "Индексы и оптимизация запросов", "level": "medium", "order": 4,
                     "content": "Индексы: B-tree, Hash, GIN, GiST. Составные индексы, covering index. EXPLAIN ANALYZE. Оптимизация: избегание SELECT *, правильные JOIN, использование LIMIT.",
                     "task": "Проанализируйте медленный запрос через EXPLAIN ANALYZE. Предложите индексы для оптимизации. Замерьте время до и после."},
                    {"name": "Транзакции: ACID, уровни изоляции", "level": "advanced", "order": 5,
                     "content": "ACID: Atomicity, Consistency, Isolation, Durability. Уровни изоляции: READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE. Deadlocks, optimistic locking.",
                     "task": "Опишите сценарий с конкурентным доступом (бронирование билетов). Какой уровень изоляции выбрать? Как предотвратить овербукинг?"},
                    {"name": "NoSQL: MongoDB, Redis, ключ-значение", "level": "medium", "order": 6,
                     "content": "CAP-теорема. Документные БД: MongoDB (коллекции, документы, запросы). Key-Value: Redis (строки, хеши, списки, множества). Графовые БД: Neo4j. Выбор типа БД.",
                     "task": "Перенесите часть данных из реляционной БД в Redis (кэш сессий) и MongoDB (логи действий). Объясните выбор типа хранилища."},
                    {"name": "Репликация и шардирование", "level": "advanced", "order": 7,
                     "content": "Репликация: master-slave, master-master, синхронная/асинхронная. Шардирование: hash-based, range-based, directory-based. Консистентное хеширование. Read replicas.",
                     "task": "Спроектируйте стратегию масштабирования БД для сервиса с 10M пользователей. Определите ключи шардирования и стратегию репликации."},
                    {"name": "Резервное копирование и восстановление", "level": "basic", "order": 8,
                     "content": "Бэкапы: полный, инкрементальный, дифференциальный. pg_dump/pg_restore (PostgreSQL), mysqldump. Автоматизация через cron. Point-in-Time Recovery (PITR). WAL-архивация.",
                     "task": "Настройте автоматическое резервное копирование PostgreSQL: ежедневный pg_dump, ротация (хранить 7 дней), тест восстановления."},
                    {"name": "Миграции схем и версионирование БД", "level": "medium", "order": 9,
                     "content": "Миграции: Alembic (Python), Flyway (Java), Knex (Node.js). Версионирование схемы. Обратная совместимость. Blue-green migrations. Zero-downtime изменения.",
                     "task": "Создайте миграцию для добавления новой таблицы и изменения существующей. Обеспечьте возможность отката (downgrade)."},
                    {"name": "Безопасность: SQL-инъекции, привилегии, шифрование", "level": "advanced", "order": 10,
                     "content": "SQL-инъекции: примеры, параметризованные запросы. Привилегии: GRANT, REVOKE, роли. Шифрование данных: at rest, in transit. Аудит, маскирование PII.",
                     "task": "Проведите аудит безопасности базы данных: найдите уязвимости к SQL-инъекциям, настройте минимальные привилегии, зашифруйте чувствительные данные."},
                ],
            },
            {
                "name": "QA и тестирование",
                "desc": "Теория тестирования, автоматизация, CI/CD интеграция",
                "topics": [
                    {"name": "Теория тестирования: виды, уровни, пирамида", "level": "basic", "order": 1,
                     "content": "Виды тестирования: функциональное, нефункциональное, регрессионное.  Уровни: unit, integration, system, acceptance. Пирамида тестирования. Тест-дизайн: эквивалентные классы, граничные значения.",
                     "task": "Составьте матрицу тестирования для интернет-магазина: определите виды тестов, уровни, приоритеты. Нарисуйте пирамиду тестирования проекта."},
                    {"name": "Тест-кейсы и чек-листы", "level": "basic", "order": 2,
                     "content": "Тест-кейсы: id, шаги, ожидаемый результат, приоритет. Чек-листы для smoke/sanity тестирования. Баг-репорты: severity, priority, шаги воспроизведения. Тест-планы.",
                     "task": "Напишите 10 тест-кейсов для формы регистрации (позитивные и негативные) и чек-лист для smoke-тестирования главной страницы."},
                    {"name": "Unit-тестирование: Jest, Mocha, pytest", "level": "medium", "order": 3,
                     "content": "Unit-тесты: изоляция, AAA (Arrange-Act-Assert), моки и стабы. Jest: describe, it, expect, mock. Pytest: fixtures, parametrize, conftest. Покрытие кода (coverage).",
                     "task": "Напишите unit-тесты для модуля обработки данных: минимум 10 тестов, включая edge cases. Достигните покрытия > 80%."},
                    {"name": "Интеграционное тестирование", "level": "medium", "order": 4,
                     "content": "Интеграционные тесты: проверка взаимодействия компонентов. Тестовые базы данных, тестовые контейнеры (Testcontainers). Фикстуры, сиды данных. API-тесты с реальной БД.",
                     "task": "Напишите интеграционные тесты для API: создание, чтение, обновление, удаление сущности. Используйте тестовую базу данных."},
                    {"name": "E2E тестирование: Cypress, Selenium, Playwright", "level": "advanced", "order": 5,
                     "content": "E2E тесты: имитация действий пользователя. Cypress: cy.visit, cy.get, cy.click. Playwright: page.goto, locator. Селекторы, ожидания, скриншоты. Параллельный запуск.",
                     "task": "Напишите E2E тесты для потока: регистрация → логин → создание проекта → добавление задачи → выход. Используйте Cypress или Playwright."},
                    {"name": "API тестирование: Postman, REST Assured", "level": "medium", "order": 6,
                     "content": "Тестирование API: Postman коллекции, окружения, тесты. REST Assured (Java), httpx (Python). Валидация JSON Schema. Тестирование авторизации, ошибок.",
                     "task": "Создайте Postman-коллекцию для тестирования API: CRUD, авторизация, валидация ошибок. Добавьте автотесты (pm.test) и переменные окружения."},
                    {"name": "Нагрузочное тестирование: JMeter, k6", "level": "advanced", "order": 7,
                     "content": "Нагрузочное тестирование: stress, load, spike, soak тесты. k6: сценарии на JS, metrics. JMeter: thread groups, samplers, assertions. Метрики: RPS, latency p95/p99, error rate.",
                     "task": "Проведите нагрузочное тестирование API: определите максимальный RPS, найдите узкие места, постройте график latency при разной нагрузке."},
                    {"name": "TDD и BDD методологии", "level": "advanced", "order": 8,
                     "content": "TDD: Red-Green-Refactor цикл. BDD: Given-When-Then, Gherkin синтаксис. Cucumber, Behave. ATDD (Acceptance Test Driven Development). Практики и анти-паттерны.",
                     "task": "Реализуйте функцию калькулятора по методологии TDD: сначала напишите тесты, затем реализацию. Документируйте каждый Red-Green-Refactor цикл."},
                    {"name": "Тесты в CI/CD пайплайне", "level": "medium", "order": 9,
                     "content": "Интеграция тестов в CI/CD: запуск при push/PR, параллельные тесты, отчёты. Test gates: минимальное покрытие, zero failures. Flaky tests: обнаружение и исправление.",
                     "task": "Настройте CI пайплайн с тестами: lint → unit tests → integration tests → coverage report. Добавьте gate: не мержить при покрытии < 70%."},
                    {"name": "Автоматизация: фреймворки, Page Object, отчёты", "level": "advanced", "order": 10,
                     "content": "Фреймворки автоматизации: Selenium WebDriver, Playwright, Appium. Page Object Model. Генерация отчётов: Allure, HTML reports. Параллельный запуск, cross-browser тестирование.",
                     "task": "Создайте автоматизированный тест-сьют с Page Object Model: минимум 3 страницы, 10 тестов. Настройте Allure отчёты."},
                ],
            },
        ],
    },
    {
        "name": "Управление и Стратегия",
        "directions": [
            {
                "name": "Стратегический консалтинг",
                "desc": "SWOT, бизнес-моделирование, roadmap, управление изменениями",
                "topics": [
                    {"name": "SWOT, PESTEL, Porter's 5 Forces", "level": "basic", "order": 1,
                     "content": "Инструменты стратегического анализа. SWOT: сильные/слабые стороны, возможности/угрозы. PESTEL: политические, экономические, социальные, технологические, экологические, правовые факторы. Модель 5 сил Портера.",
                     "task": "Проведите SWOT-анализ и анализ по Портеру для выбранной компании (или стартапа). Сформулируйте 3 стратегические рекомендации."},
                    {"name": "Бизнес-моделирование и Canvas", "level": "basic", "order": 2,
                     "content": "Business Model Canvas: 9 блоков (ценностное предложение, сегменты клиентов, каналы, отношения, потоки доходов, ресурсы, деятельность, партнёры, структура затрат). Lean Canvas.",
                     "task": "Заполните Business Model Canvas для нового продукта/сервиса. Определите ключевые гипотезы и способы их проверки."},
                    {"name": "Разработка стратегии и roadmap", "level": "medium", "order": 3,
                     "content": "Стратегическое планирование: видение, миссия, цели. Roadmap: квартальный, годовой. Приоритизация: ICE, RICE, MoSCoW. Балансирование краткосрочных и долгосрочных целей.",
                     "task": "Разработайте стратегический roadmap на 12 месяцев для IT-продукта: цели по кварталам, ключевые метрики, зависимости."},
                    {"name": "KPI и OKR для стратегических целей", "level": "medium", "order": 4,
                     "content": "KPI: отставшие и опережающие индикаторы. OKR: Objectives & Key Results, каскадирование. BSC (Balanced Scorecard). SMART-цели. Дашборды для отслеживания.",
                     "task": "Составьте OKR для компании на квартал: 3 цели, по 3-4 ключевых результата на каждую. Определите KPI для мониторинга."},
                    {"name": "Управление изменениями", "level": "advanced", "order": 5,
                     "content": "Модели управления изменениями: Коттер (8 шагов), ADKAR, модель Левина. Сопротивление изменениям. Коммуникация. Change Management Office. Метрики успеха трансформации.",
                     "task": "Разработайте план управления изменениями для внедрения новой CRM-системы: стейкхолдеры, этапы, коммуникация, обучение, метрики."},
                ],
            },
            {
                "name": "Управление проектами",
                "desc": "Методологии, планирование, риски, инструменты",
                "topics": [
                    {"name": "Основы PM: Waterfall, Agile, Scrum", "level": "basic", "order": 1,
                     "content": "Водопадная модель: фазы, документация. Agile: манифест, принципы. Scrum: роли (PO, SM, Team), артефакты (backlog, sprint backlog, increment), церемонии (planning, standup, review, retro).",
                     "task": "Сравните Waterfall и Scrum для проекта разработки мобильного приложения. Какую методологию выберете и почему? Опишите первый спринт."},
                    {"name": "WBS, декомпозиция, планирование", "level": "basic", "order": 2,
                     "content": "WBS (Work Breakdown Structure): уровни декомпозиции, work packages. Планирование: Gantt, сетевые диаграммы, критический путь. Оценка: Planning Poker, T-shirt sizing.",
                     "task": "Создайте WBS для проекта запуска веб-сайта. Определите критический путь и оцените сроки методом Planning Poker."},
                    {"name": "Управление рисками", "level": "medium", "order": 3,
                     "content": "Идентификация рисков: мозговой штурм, SWOT. Матрица рисков: вероятность × влияние. Стратегии: избежание, принятие, перенос, смягчение. Risk register, мониторинг.",
                     "task": "Составьте реестр рисков (минимум 10) для IT-проекта. Оцените каждый риск, определите стратегию реагирования и ответственного."},
                    {"name": "Работа со стейкхолдерами", "level": "medium", "order": 4,
                     "content": "Идентификация стейкхолдеров. Матрица власти/интереса. Стратегии коммуникации: inform, consult, involve, empower. Управление конфликтами. Reporting и статус-отчёты.",
                     "task": "Составьте карту стейкхолдеров для проекта внедрения ERP. Определите стратегию коммуникации для каждой группы."},
                    {"name": "Инструменты: Jira, MS Project, Notion", "level": "basic", "order": 5,
                     "content": "Jira: epic, story, task, bug, sprint board, backlog. MS Project: Gantt, ресурсы, зависимости. Notion: databases, views, templates. Trello: kanban. Asana: portfolios.",
                     "task": "Настройте Jira-проект для Scrum-команды: создайте board, epics, stories. Определите workflow (To Do → In Progress → Review → Done)."},
                    {"name": "Масштабирование: SAFe, LeSS", "level": "advanced", "order": 6,
                     "content": "Масштабирование Agile: SAFe (PI Planning, ART, Value Streams), LeSS (Sprint Planning 1&2, Overall Retro), Nexus, Spotify Model. Когда масштабировать, а когда нет.",
                     "task": "Предложите модель масштабирования для организации с 5 Scrum-командами, работающими над одним продуктом. Спланируйте PI Planning."},
                ],
            },
            {
                "name": "Цифровая трансформация",
                "desc": "Аудит цифровой зрелости, автоматизация, data-driven решения",
                "topics": [
                    {"name": "Аудит цифровой зрелости", "level": "basic", "order": 1,
                     "content": "Модели цифровой зрелости: DMM, BCG Digital Acceleration Index. Оценка текущего состояния: процессы, технологии, культура, данные. Gap-анализ. Benchmarking.",
                     "task": "Проведите аудит цифровой зрелости для выбранной компании по 5 измерениям. Определите текущий уровень и целевое состояние."},
                    {"name": "Roadmap цифровой трансформации", "level": "medium", "order": 2,
                     "content": "Этапы трансформации: digitization → digitalization → digital transformation. Выбор инициатив, Quick Wins vs стратегические проекты. ROI цифровых инициатив. Change management.",
                     "task": "Разработайте roadmap цифровой трансформации на 2 года: фазы, инициативы, KPI, бюджет, команда."},
                    {"name": "Автоматизация бизнес-процессов", "level": "medium", "order": 3,
                     "content": "Моделирование процессов: BPMN 2.0. Автоматизация: RPA (UiPath, Automation Anywhere), low-code (Mendix, Power Apps), no-code. Критерии выбора процессов для автоматизации.",
                     "task": "Выберите 3 бизнес-процесса для автоматизации. Опишите текущий и целевой процесс (as-is / to-be), инструменты и ожидаемый эффект."},
                    {"name": "Data-driven принятие решений", "level": "advanced", "order": 4,
                     "content": "Культура данных: data literacy, data governance. BI инструменты: Power BI, Tableau, Metabase. Метрики и KPI. A/B тестирование для бизнес-решений. Data pipeline.",
                     "task": "Постройте дашборд для принятия решений: 5 ключевых метрик бизнеса, визуализации, автоматическое обновление данных."},
                ],
            },
        ],
    },
    {
        "name": "Маркетинг",
        "directions": [
            {
                "name": "Маркетинговая стратегия",
                "desc": "Анализ рынка, сегментация, брендинг, планирование",
                "topics": [
                    {"name": "Анализ рынка и конкурентов", "level": "basic", "order": 1,
                     "content": "Методы анализа рынка: TAM, SAM, SOM. Конкурентный анализ: прямые/непрямые конкуренты, матрица сравнения. Mystery shopping. Тренды и прогнозирование.",
                     "task": "Проведите анализ рынка и минимум 5 конкурентов для выбранного продукта/сервиса. Составьте матрицу сравнения."},
                    {"name": "Сегментация ЦА и позиционирование", "level": "basic", "order": 2,
                     "content": "Сегментация: демографическая, поведенческая, психографическая. Персоны (Buyer Persona). Позиционирование: карта позиционирования, USP. Jobs To Be Done (JTBD).",
                     "task": "Создайте 3 персоны целевой аудитории для продукта. Постройте карту позиционирования относительно конкурентов."},
                    {"name": "Формулирование УТП", "level": "medium", "order": 3,
                     "content": "Уникальное торговое предложение (УТП): формулирование, тестирование. Value Proposition Canvas. Elevator Pitch. Messaging framework: заголовки, подзаголовки, proof points.",
                     "task": "Разработайте УТП для продукта: заполните Value Proposition Canvas. Напишите 3 варианта elevator pitch и протестируйте на целевой аудитории."},
                    {"name": "Брендинг и бренд-стратегия", "level": "medium", "order": 4,
                     "content": "Бренд-платформа: миссия, ценности, tone of voice. Brand Book: логотип, типографика, палитра. Brand Equity: осведомлённость, лояльность, ассоциации. Ребрендинг.",
                     "task": "Разработайте бренд-платформу: миссия, ценности, архетип, tone of voice, визуальный стиль. Создайте мини brand book."},
                    {"name": "Маркетинговый план и бюджетирование", "level": "advanced", "order": 5,
                     "content": "Маркетинговый план: цели, стратегия, тактика, KPI, бюджет. Распределение бюджета по каналам. Медиаплан. ROI маркетинга. Сезонность и тайминг.",
                     "task": "Составьте маркетинговый план на 6 месяцев: каналы, бюджет, KPI, календарь активностей, прогноз ROI."},
                ],
            },
            {
                "name": "Performance-маркетинг",
                "desc": "Контекстная и таргетированная реклама, аналитика, оптимизация",
                "topics": [
                    {"name": "Контекстная реклама: Google Ads, Яндекс Директ", "level": "basic", "order": 1,
                     "content": "Контекстная реклама: поисковая, КМС/РСЯ. Структура аккаунта: кампания → группа → объявление. Ключевые слова: match types, минус-слова. Ставки и стратегии. Качество объявления.",
                     "task": "Создайте структуру рекламной кампании в Google Ads или Яндекс Директ: 3 группы по 5 ключевых слов, объявления, минус-слова."},
                    {"name": "Таргетированная реклама: Meta, VK, TikTok", "level": "basic", "order": 2,
                     "content": "Таргетированная реклама: аудитории (интересы, lookalike, ретаргетинг). Форматы: карусель, видео, stories. Воронка: awareness → consideration → conversion. Пиксель и events.",
                     "task": "Настройте рекламную кампанию в VK или Meta: 3 аудитории (холодная, тёплая, ретаргетинг), создайте объявления для каждого этапа воронки."},
                    {"name": "Аналитика: GA4, Яндекс Метрика, UTM", "level": "medium", "order": 3,
                     "content": "Google Analytics 4: события, конверсии, когорты, воронки. Яндекс Метрика: вебвизор, карта кликов, карта скроллов. UTM-метки: source, medium, campaign. Атрибуция.",
                     "task": "Настройте GA4 для сайта: цели (конверсии), воронку покупки, UTM-разметку для 3 каналов. Создайте дашборд с ключевыми метриками."},
                    {"name": "A/B тестирование и оптимизация", "level": "medium", "order": 4,
                     "content": "A/B тестирование: гипотеза, split, статистическая значимость, sample size. Мультивариантное тестирование. CRO (Conversion Rate Optimization): landing pages, CTA, формы.",
                     "task": "Проведите A/B тест для landing page: сформулируйте гипотезу, определите метрику, рассчитайте необходимый sample size, проанализируйте результаты."},
                    {"name": "ROMI, CPA, LTV, unit-экономика", "level": "advanced", "order": 5,
                     "content": "Unit-экономика: CAC, LTV, LTV/CAC ratio. ROMI/ROAS расчёт. Когортный анализ. Payback period. Масштабирование: когда увеличивать бюджет. Маржинальность каналов.",
                     "task": "Рассчитайте unit-экономику для продукта: CAC по каналам, LTV, payback period. Определите, какие каналы масштабировать, а какие отключить."},
                ],
            },
            {
                "name": "Контент и SMM",
                "desc": "Контент-стратегия, копирайтинг, SMM, SEO, email",
                "topics": [
                    {"name": "Контент-стратегия и план", "level": "basic", "order": 1,
                     "content": "Контент-маркетинг: цели, форматы (статьи, видео, подкасты, инфографика). Контент-план: рубрикатор, частота, платформы. Content Pillars. Контент-матрица: awareness/consideration/decision.",
                     "task": "Разработайте контент-стратегию на месяц: контент-столбы, рубрикатор, календарь публикаций для 3 платформ."},
                    {"name": "Копирайтинг и редактура", "level": "basic", "order": 2,
                     "content": "Копирайтинг: AIDA, PAS, 4U формулы. Заголовки: числа, вопросы, how-to. Tone of Voice. Информационный стиль (Ильяхов). Редактура: главред, чек-лист качества.",
                     "task": "Напишите 5 текстов для разных форматов: пост в соцсети, email-рассылка, описание продукта, статья в блог, рекламное объявление."},
                    {"name": "SMM: ведение соцсетей", "level": "basic", "order": 3,
                     "content": "Платформы: Telegram, VK, Instagram*, YouTube, TikTok. Контент-план для соцсетей. Engagement: лайки, комментарии, репосты, ERR. Community management. UGC контент.",
                     "task": "Создайте SMM-стратегию: выбор платформ, tone of voice, рубрики, KPI. Подготовьте 10 публикаций на 2 недели."},
                    {"name": "SEO: on-page, off-page, техническое", "level": "medium", "order": 4,
                     "content": "SEO: on-page (meta tags, headings, content), off-page (ссылки, PR), техническое (скорость, мобильность, sitemap, robots.txt). Семантическое ядро. Поисковые запросы: ВЧ, СЧ, НЧ.",
                     "task": "Проведите SEO-аудит сайта: техническая оптимизация, анализ контента, семантическое ядро (50 запросов). Составьте план оптимизации."},
                    {"name": "Email-маркетинг и автоворонки", "level": "medium", "order": 5,
                     "content": "Email-маркетинг: базы подписчиков, сегментация, персонализация. Типы писем: welcome-серия, прогревающие, транзакционные. Автоворонки. Метрики: open rate, CTR, unsubscribe. Сервисы: Unisender, SendPulse.",
                     "task": "Создайте автоматическую email-воронку из 5 писем: welcome → обучение → кейс → оффер → дожим. Определите триггеры и сегменты."},
                ],
            },
        ],
    },
    {
        "name": "Финансы и учёт",
        "directions": [
            {
                "name": "Управленческий учёт",
                "desc": "P&L, Cash Flow, баланс, бюджетирование",
                "topics": [
                    {"name": "P&L: структура, анализ", "level": "basic", "order": 1,
                     "content": "Отчёт о прибылях и убытках (P&L): выручка, себестоимость, валовая прибыль, операционные расходы, EBITDA, чистая прибыль. Вертикальный и горизонтальный анализ. Маржинальность.",
                     "task": "Составьте и проанализируйте P&L за квартал: определите маржинальность, динамику расходов, точку безубыточности."},
                    {"name": "Cash Flow: прямой и косвенный метод", "level": "medium", "order": 2,
                     "content": "Отчёт о движении денежных средств: операционный, инвестиционный, финансовый денежный поток. Прямой и косвенный метод построения. Кассовый разрыв. Working capital management.",
                     "task": "Постройте Cash Flow прямым и косвенным методом. Определите кассовые разрывы и предложите меры по управлению ликвидностью."},
                    {"name": "Управленческий баланс", "level": "medium", "order": 3,
                     "content": "Баланс: активы (оборотные и внеоборотные), пассивы (собственный капитал, обязательства). Коэффициенты: текущей ликвидности, автономии, ROE, ROA. Управленческий vs бухгалтерский баланс.",
                     "task": "Составьте упрощённый управленческий баланс. Рассчитайте ключевые коэффициенты и дайте рекомендации по улучшению финансового здоровья."},
                    {"name": "Бюджетирование и план-факт", "level": "advanced", "order": 4,
                     "content": "Бюджетирование: top-down vs bottom-up. Виды бюджетов: БДР, БДДС, CapEx. План-факт анализ: отклонения, причины, корректировки. Rolling forecast. Zero-based budgeting.",
                     "task": "Составьте бюджет компании на квартал (БДР и БДДС). Проведите план-факт анализ за прошлый период и определите зоны для оптимизации."},
                ],
            },
            {
                "name": "Налоговый консалтинг",
                "desc": "Налоговая система, оптимизация, риски и проверки",
                "topics": [
                    {"name": "Налоговая система: виды налогов, режимы", "level": "basic", "order": 1,
                     "content": "Налоговая система РФ: федеральные, региональные, местные налоги. Режимы: ОСНО, УСН (6% / 15%), АУСН, ПСН, ЕСХН. НДС, налог на прибыль, НДФЛ, страховые взносы.",
                     "task": "Сравните налоговые режимы (ОСНО, УСН 6%, УСН 15%) для компании с заданными параметрами (выручка, расходы, ФОТ). Определите оптимальный режим."},
                    {"name": "Оптимизация налоговой нагрузки", "level": "medium", "order": 2,
                     "content": "Законные способы оптимизации: выбор режима, ИП vs ООО, амортизация, резервы, вычеты НДС. IT-льготы. Региональные льготы. Дробление бизнеса — риски.",
                     "task": "Проведите анализ налоговой нагрузки компании и предложите 3-5 законных способов оптимизации с расчётом экономии."},
                    {"name": "Налоговые риски и проверки", "level": "advanced", "order": 3,
                     "content": "Виды проверок: камеральная, выездная, встречная. Критерии отбора для проверки (12 критериев ФНС). Налоговые риски: трансфертное ценообразование, сомнительные контрагенты. Обжалование.",
                     "task": "Проведите самопроверку компании по 12 критериям ФНС. Определите зоны рисков и составьте план по их минимизации."},
                ],
            },
            {
                "name": "Инвестиционный анализ",
                "desc": "DCF, мультипликаторы, Due Diligence, сценарный анализ",
                "topics": [
                    {"name": "DCF-модель и дисконтирование", "level": "medium", "order": 1,
                     "content": "DCF (Discounted Cash Flow): прогноз свободного денежного потока, ставка дисконтирования (WACC), терминальная стоимость. NPV, IRR, PBP. Чувствительность к параметрам.",
                     "task": "Постройте DCF-модель для инвестиционного проекта: прогноз на 5 лет, расчёт WACC, NPV, IRR. Проведите анализ чувствительности."},
                    {"name": "Мультипликаторы: P/E, EV/EBITDA", "level": "basic", "order": 2,
                     "content": "Мультипликаторы: P/E, P/S, EV/EBITDA, EV/Revenue, P/BV. Сравнительная оценка: выбор аналогов, медианный мультипликатор. Справедливая стоимость. Ограничения метода.",
                     "task": "Оцените компанию методом мультипликаторов: подберите 5 аналогов, рассчитайте медианные мультипликаторы, определите справедливую стоимость."},
                    {"name": "Due Diligence", "level": "advanced", "order": 3,
                     "content": "Due Diligence: финансовый, юридический, tax DD, операционный, IT DD. Checklist, red flags. Качество прибыли (Quality of Earnings). Структурирование сделки.",
                     "task": "Составьте чек-лист финансового Due Diligence для приобретения IT-компании. Определите 10 ключевых red flags."},
                    {"name": "Сценарный анализ", "level": "advanced", "order": 4,
                     "content": "Сценарный анализ: базовый, оптимистичный, пессимистичный сценарии. Monte Carlo simulation. Стресс-тестирование. Визуализация результатов. Принятие решений в условиях неопределённости.",
                     "task": "Проведите сценарный анализ для инвестиционного проекта: 3 сценария с разными предположениями. Рассчитайте вероятностное распределение NPV."},
                ],
            },
        ],
    },
    {
        "name": "Кадры и организация (HR)",
        "directions": [
            {
                "name": "Подбор персонала",
                "desc": "Сорсинг, интервью, HR-бренд, адаптация",
                "topics": [
                    {"name": "Сорсинг и каналы привлечения", "level": "basic", "order": 1,
                     "content": "Каналы привлечения: job boards (hh.ru, LinkedIn), соцсети, реферальная программа, кадровые агентства. Сорсинг: boolean search, LinkedIn Recruiter. Воронка подбора: TTF, CPH.",
                     "task": "Составьте стратегию привлечения для вакансии: 5 каналов, бюджет, ожидаемая воронка (конверсии на каждом этапе), TTF."},
                    {"name": "Проведение интервью и оценка", "level": "basic", "order": 2,
                     "content": "Типы интервью: структурированное, поведенческое (STAR), кейсовое, техническое. Оценка: scorecards, компетенции, soft skills. Assessment center. Bias-free hiring.",
                     "task": "Разработайте структуру интервью для должности PM: 10 вопросов (STAR), rubrics для оценки, scorecard. Проведите mock-интервью."},
                    {"name": "HR-бренд и EVP", "level": "medium", "order": 3,
                     "content": "HR-бренд: внутренний и внешний. EVP (Employee Value Proposition): компоненты, уникальность. Employer Branding: каналы, контент, мероприятия. Glassdoor, отзывы. Метрики.",
                     "task": "Разработайте EVP для компании: исследуйте текущее восприятие, определите 5 ключевых элементов, создайте коммуникационный план."},
                    {"name": "Адаптация и онбординг", "level": "medium", "order": 4,
                     "content": "Онбординг: pre-boarding, первый день, первая неделя, первый месяц, 90 дней. Buddy system, mentoring. Чек-листы. Метрики: time-to-productivity, retention 90 дней. Обратная связь.",
                     "task": "Разработайте программу онбординга на 90 дней: чек-листы по неделям, buddy program, контрольные точки, метрики успеха."},
                ],
            },
            {
                "name": "Обучение и развитие (L&D)",
                "desc": "Потребности, программы, LMS, развитие лидерства",
                "topics": [
                    {"name": "Выявление потребностей в обучении", "level": "basic", "order": 1,
                     "content": "Training Needs Analysis (TNA): организационный, командный, индивидуальный уровень. Методы: опросы, интервью, оценка компетенций, анализ KPI. Gap-анализ. Матрица компетенций.",
                     "task": "Проведите TNA для отдела (10 человек): создайте матрицу компетенций, определите gaps, сформируйте план обучения с приоритетами."},
                    {"name": "Разработка программ обучения", "level": "medium", "order": 2,
                     "content": "Модель ADDIE: анализ, дизайн, разработка, внедрение, оценка. Bloom's Taxonomy. Форматы: очное, онлайн, blended, microlearning. Вовлечение: геймификация, practice-based. Контент: внутренний vs внешний.",
                     "task": "Разработайте программу обучения по модели ADDIE: тема на выбор, 5 модулей, материалы, практические задания, критерии оценки."},
                    {"name": "LMS и платформы обучения", "level": "medium", "order": 3,
                     "content": "LMS: Moodle, iSpring, GetCourse, собственные решения. Функции: курсы, тесты, сертификаты, аналитика. SCORM/xAPI стандарты. Геймификация: бейджи, рейтинги. Мобильное обучение.",
                     "task": "Сравните 3 LMS-платформы по критериям: функционал, стоимость, интеграции, UX. Выберите оптимальную и обоснуйте."},
                    {"name": "Развитие лидерства и кадровый резерв", "level": "advanced", "order": 4,
                     "content": "Модели лидерства: ситуационное, трансформационное, servant leadership. Кадровый резерв: HiPo идентификация, 9-box grid. Succession planning. Менторинг, коучинг, 360 feedback.",
                     "task": "Разработайте программу развития кадрового резерва: критерии отбора HiPo, 9-box grid для оценки, индивидуальные планы развития, менторинг."},
                ],
            },
            {
                "name": "Компенсации и льготы (C&B)",
                "desc": "Грейдирование, мотивация, соцпакет",
                "topics": [
                    {"name": "Грейдирование и уровни", "level": "medium", "order": 1,
                     "content": "Грейдирование должностей: Hay, Mercer, внутренние системы. Иерархия уровней: junior/middle/senior/lead. Вилки зарплат. Рыночные обзоры: hh, Glassdoor салаири. Job evaluation.",
                     "task": "Разработайте систему грейдов для IT-компании (15 должностей): критерии оценки, уровни, вилки зарплат на основе рыночных данных."},
                    {"name": "KPI и системы мотивации", "level": "medium", "order": 2,
                     "content": "Системы мотивации: фикс + бонус, OKR-based, KPI-based. Переменная часть: процент от выручки, project bonus, stock options. Нематериальная мотивация. Performance review.",
                     "task": "Разработайте систему мотивации для sales-команды и dev-команды: KPI, формула бонуса, периодичность, ограничения. Сравните подходы."},
                    {"name": "ДМС, бенефиты, соцпакет", "level": "basic", "order": 3,
                     "content": "Соцпакет: ДМС, питание, фитнес, обучение, удалённая работа, гибкий график. Бенефиты: cafeteria plan, персонализация. Wellbeing программы. Анализ затрат и ROI бенефитов.",
                     "task": "Спроектируйте cafeteria plan с бюджетом 30 000 ₽/мес на сотрудника: категории бенефитов, варианты выбора, администрирование."},
                ],
            },
        ],
    },
]


async def seed():
    """Заполнение базы данных курсами обучения."""
    async with async_session() as db:
        # Найти admin-пользователя
        result = await db.execute(
            select(User).where(User.role == UserRole.ADMIN).limit(1)
        )
        admin = result.scalar_one_or_none()
        if not admin:
            print("❌ Не найден admin-пользователь. Создайте его сначала.")
            return

        # Удалить существующие курсы (cascade удалит темы, контент, задания)
        existing = await db.execute(select(TrainingCourse))
        old_courses = existing.scalars().all()
        if old_courses:
            for c in old_courses:
                await db.delete(c)
            await db.commit()
            print(f"🗑️  Удалено {len(old_courses)} старых курсов")

        print(f"👤 Используется admin: {admin.email}")

        course_order = 0
        total_courses = 0
        total_topics = 0
        total_content = 0
        total_tasks = 0

        for sphere in SPHERES:
            sphere_name = sphere["name"]
            print(f"\n📚 Сфера: {sphere_name}")

            for direction in sphere["directions"]:
                # Каждое направление — курс
                course = TrainingCourse(
                    title=f"{direction['name']}",
                    description=f"{sphere_name} → {direction['name']}\n{direction['desc']}",
                    order=course_order,
                    is_published=True,
                    created_by=admin.id,
                )
                db.add(course)
                await db.flush()  # чтобы получить course.id
                course_order += 1
                total_courses += 1
                print(f"  📖 Курс: {direction['name']} ({len(direction['topics'])} тем)")

                for topic_data in direction["topics"]:
                    # Тема
                    topic = TrainingTopic(
                        course_id=course.id,
                        title=topic_data["name"],
                        description=f"Уровень: {_level_label(topic_data['level'])}",
                        order=topic_data["order"] - 1,  # 0-based
                    )
                    db.add(topic)
                    await db.flush()
                    total_topics += 1

                    # Контент-блок с теорией
                    content = TrainingContent(
                        topic_id=topic.id,
                        title="Теория",
                        body=topic_data["content"],
                        order=0,
                    )
                    db.add(content)
                    total_content += 1

                    # Практическое задание
                    task = TrainingTask(
                        topic_id=topic.id,
                        title=f"Практика: {topic_data['name']}",
                        description=topic_data["task"],
                    )
                    db.add(task)
                    total_tasks += 1

        await db.commit()
        print(f"\n✅ Готово!")
        print(f"   Курсов: {total_courses}")
        print(f"   Тем: {total_topics}")
        print(f"   Блоков контента: {total_content}")
        print(f"   Заданий: {total_tasks}")


def _level_label(level: str) -> str:
    return {"basic": "Базовый", "medium": "Средний", "advanced": "Продвинутый"}.get(level, level)


if __name__ == "__main__":
    asyncio.run(seed())
