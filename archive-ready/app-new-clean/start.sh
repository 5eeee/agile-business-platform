#!/usr/bin/env bash
# ============================================================
# Agile Business -- Universal Launcher (macOS / Linux)
# Usage: ./start.sh            (auto-detect)
#        ./start.sh --docker   (force Docker)
#        ./start.sh --local    (force local dev)
#        ./start.sh --stop     (stop containers)
# ============================================================

set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "  Agile Business -- Launcher"
echo "========================================"
echo ""

# ── Try Python launcher ──
for PY in python3 python; do
    if command -v "$PY" &>/dev/null; then
        VER=$("$PY" --version 2>&1 || true)
        if echo "$VER" | grep -q "Python 3"; then
            echo "[OK] $PY found ($VER)"
            exec "$PY" start.py "$@"
        fi
    fi
done

# ── No Python: fallback to Docker directly ──
echo "[!] Python 3 not found, trying Docker directly..."
echo ""

if ! command -v docker &>/dev/null; then
    echo "[ERROR] Neither Python 3 nor Docker found!"
    echo ""
    echo "Install one of:"
    echo "  Python 3.10+:     https://www.python.org/downloads/"
    echo "  Docker Desktop:   https://www.docker.com/products/docker-desktop/"
    echo ""
    exit 1
fi

# Check/create .env
if [ ! -f ".env" ]; then
    SECRET=$(head -c 48 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)
    cat > .env << ENVEOF
DEBUG=false
SECRET_KEY=${SECRET}
DOMAIN=localhost
DB_PASSWORD=agile_local_pass
REDIS_PASSWORD=agile_redis_pass
MINIO_USER=minioadmin
MINIO_PASSWORD=minioadmin123
ELASTIC_PASSWORD=changeme
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
ADMIN_SEED_EMAIL=admin@agile.local
ADMIN_SEED_PASSWORD=admin123
WORKERS=2
FRONTEND_PORT=3000
ENVEOF
    echo "[OK] .env created with local defaults"
fi

echo "Starting with Docker Compose..."
docker compose up -d --build --remove-orphans

echo ""
echo "Waiting for site to start..."
sleep 30

# Open browser
URL="http://localhost:3000"
echo "Opening browser: $URL"
if command -v xdg-open &>/dev/null; then
    xdg-open "$URL" 2>/dev/null &
elif command -v open &>/dev/null; then
    open "$URL" 2>/dev/null &
fi

echo ""
echo "========================================"
echo "  Site running at $URL"
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Keep alive (Ctrl+C to stop)
trap 'docker compose down; exit 0' INT TERM
while true; do sleep 10; done
