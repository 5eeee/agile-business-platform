@echo off
chcp 65001 >nul 2>&1
title Agile Business -- Launcher

echo.
echo ========================================
echo   Agile Business -- Windows Launcher
echo ========================================
echo.

cd /d "%~dp0"

:: ── Check Python ──
where python >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python found
    python start.py %*
    goto :end
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python3 found
    python3 start.py %*
    goto :end
)

:: ── No Python: try Docker directly ──
echo [!] Python not found, trying Docker directly...
echo.

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Neither Python nor Docker found!
    echo.
    echo Install one of:
    echo   Python 3.10+:     https://www.python.org/downloads/
    echo   Docker Desktop:   https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

:: Check/create .env
if not exist ".env" (
    echo Creating .env with local defaults...
    (
        echo DEBUG=false
        echo SECRET_KEY=auto_generated_%RANDOM%%RANDOM%%RANDOM%
        echo DOMAIN=localhost
        echo DB_PASSWORD=agile_local_pass
        echo REDIS_PASSWORD=agile_redis_pass
        echo MINIO_USER=minioadmin
        echo MINIO_PASSWORD=minioadmin123
        echo ELASTIC_PASSWORD=changeme
        echo CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
        echo ADMIN_SEED_EMAIL=admin@agile.local
        echo ADMIN_SEED_PASSWORD=admin123
        echo WORKERS=2
        echo FRONTEND_PORT=3000
    ) > .env
    echo [OK] .env created
)

echo Starting with Docker Compose...
docker compose up -d --build --remove-orphans

echo.
echo Waiting for site to start...
timeout /t 30 /nobreak >nul

echo Opening browser...
start http://localhost:3000

echo.
echo ========================================
echo   Site running at http://localhost:3000
echo   Press Ctrl+C or close window to stop
echo ========================================
echo.

:wait_loop
timeout /t 10 /nobreak >nul
goto :wait_loop

:end
pause
