#!/usr/bin/env python3
"""
Деплой Agile Business на VPS (PostgreSQL, Docker).
Credentials из .env: VPS_HOST, VPS_USER, VPS_PASSWORD, DEPLOY_DOMAIN
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Загрузка .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\"").strip())

VPS_HOST = os.environ.get("VPS_HOST", "89.104.67.148")
VPS_USER = os.environ.get("VPS_USER", "root")
VPS_PASSWORD = os.environ.get("VPS_PASSWORD", "")
DOMAIN = os.environ.get("DEPLOY_DOMAIN", "app.agile-business-pro.com")
REMOTE_PATH = "/opt/agile"


def main():
    print(f"\n=== Agile Business — Деплой на VPS ===")
    print(f"  {VPS_USER}@{VPS_HOST} | {DOMAIN}\n")

    try:
        import paramiko
    except ImportError:
        print("Установите paramiko: pip install paramiko")
        sys.exit(1)

    if not VPS_PASSWORD:
        key_path = os.path.expanduser("~/.ssh/id_rsa")
        if not os.path.isfile(key_path):
            key_path = os.path.expanduser("~/.ssh/id_ed25519")
        if not os.path.isfile(key_path):
            print("Задайте VPS_PASSWORD в .env (пароль root от VPS)")
            sys.exit(1)
        print("Используется SSH-ключ (без пароля)")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if VPS_PASSWORD:
            client.connect(VPS_HOST, port=22, username=VPS_USER, password=VPS_PASSWORD, timeout=15)
        else:
            client.connect(VPS_HOST, port=22, username=VPS_USER, timeout=15)
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        sys.exit(1)

    def run(cmd, timeout=120):
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return out, err, code

    print(">> 1. Создание директории...")
    run(f"mkdir -p {REMOTE_PATH}")

    print(">> 2. Загрузка файлов (SFTP)...")
    base = os.path.dirname(os.path.abspath(__file__))
    sftp = client.open_sftp()

    def upload_path(local_path, remote_path):
        if os.path.isfile(local_path):
            run(f"mkdir -p {os.path.dirname(remote_path)}")
            sftp.put(local_path, remote_path)
        else:
            run(f"mkdir -p {remote_path}")
            for root, dirs, files in os.walk(local_path):
                for skip in ("__pycache__", "node_modules", ".git"):
                    if skip in dirs:
                        dirs.remove(skip)
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    lp = os.path.join(root, f)
                    rp = remote_path + "/" + lp[len(local_path) + 1:].replace("\\", "/")
                    run(f"mkdir -p {os.path.dirname(rp)}")
                    sftp.put(lp, rp)

    items = ["server", "client-new", "docker-compose.prod.yml", "db-backup.sh", ".env.example"]
    for item in items:
        local = os.path.join(base, item)
        if os.path.exists(local):
            upload_path(local, f"{REMOTE_PATH}/{item}")
            print(f"   OK: {item}")
    sftp.close()

    print(">> 3. Настройка и запуск на сервере...")
    # Генерируем пароли (простая random)
    import secrets
    db_pass = secrets.token_urlsafe(24)
    redis_pass = secrets.token_urlsafe(24)
    minio_pass = secrets.token_urlsafe(24)
    secret_key = secrets.token_urlsafe(48)
    admin_pass = secrets.token_urlsafe(16)

    setup = f"""
set -e
cd {REMOTE_PATH}
cp docker-compose.prod.yml docker-compose.yml
if [ ! -f .env ]; then
  cat > .env << 'ENVEOF'
DEBUG=false
SECRET_KEY={secret_key}
DOMAIN={DOMAIN}
DB_PASSWORD={db_pass}
REDIS_PASSWORD={redis_pass}
MINIO_USER=agile-minio
MINIO_PASSWORD={minio_pass}
FRONTEND_PORT=80
ADMIN_SEED_EMAIL=admin@agile.com
ADMIN_SEED_PASSWORD={admin_pass}
CORS_ORIGINS=["https://{DOMAIN}","http://{DOMAIN}","https://{VPS_HOST}","http://{VPS_HOST}"]
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
ENVEOF
  chmod 600 .env
  echo '[OK] .env создан'
else
  echo '[OK] .env существует'
fi
mkdir -p backups
chmod +x db-backup.sh 2>/dev/null || true
echo 'Сборка Docker...'
docker compose build
docker compose up -d
echo 'Ожидание backend...'
sleep 30
echo 'Сиды курса и магазина...'
docker compose run --rm backend python seed_fullstack.py 2>/dev/null || true
docker compose run --rm backend python seed_shop_items.py 2>/dev/null || true
(crontab -l 2>/dev/null | grep -v db-backup; echo "0 3 * * * {REMOTE_PATH}/db-backup.sh >> {REMOTE_PATH}/backups/cron.log 2>&1") | crontab -
echo ''
echo '=== ДЕПЛОЙ ЗАВЕРШЁН ==='
echo "Сайт: https://{DOMAIN}"
echo "Admin: admin@agile.com / {admin_pass}"
echo "DB: agile_workspace"
"""

    out, err, code = run(setup, timeout=600)
    print(out)
    if err:
        print("stderr:", err[:500])
    if code != 0:
        print("Код выхода:", code)
        sys.exit(1)

    client.close()
    print("\n=== Готово! ===")
    print(f"Сайт: https://{DOMAIN}")
    print(f"Admin: admin@agile.com / {admin_pass}")
    print("Сохраните пароли!")


if __name__ == "__main__":
    main()
