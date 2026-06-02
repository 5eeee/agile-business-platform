"""SSH probe helper — учётные данные только из окружения (без хардкода в репозитории)."""
import paramiko
import os
import sys

HOST = os.environ.get("DEPLOY_SSH_HOST", "").strip()
USER = os.environ.get("DEPLOY_SSH_USER", "").strip()
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "").strip()
PORT = int(os.environ.get("DEPLOY_SSH_PORT", "22") or "22")

def ssh_exec(client, cmd, timeout=30):
    """Execute command and return stdout"""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return out, err, code

def main():
    if not HOST or not USER or not PASSWORD:
        print(
            "Задайте переменные окружения: DEPLOY_SSH_HOST, DEPLOY_SSH_USER, DEPLOY_SSH_PASSWORD "
            "(опционально DEPLOY_SSH_PORT)."
        )
        sys.exit(1)
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)
    print("Connected!\n")

    # Install SSH key for future passwordless access
    pub_key_path = os.path.expanduser("~/.ssh/id_ed25519.pub")
    if os.path.exists(pub_key_path):
        with open(pub_key_path) as f:
            pub_key = f.read().strip()
        ssh_exec(client, "mkdir -p ~/.ssh && chmod 700 ~/.ssh")
        out, _, _ = ssh_exec(client, "cat ~/.ssh/authorized_keys 2>/dev/null || echo ''")
        if pub_key not in out:
            ssh_exec(client, f'echo "{pub_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys')
            print("[OK] SSH key installed\n")
        else:
            print("[OK] SSH key already installed\n")

    # Probe server capabilities
    commands = {
        "OS": "cat /etc/os-release 2>/dev/null | head -3",
        "Python": "python3 --version 2>&1; which python3 2>&1",
        "Node": "node --version 2>&1; which node 2>&1",
        "npm": "npm --version 2>&1",
        "Docker": "docker --version 2>&1",
        "pip": "pip3 --version 2>&1",
        "PostgreSQL client": "psql --version 2>&1",
        "MySQL": "mysql --version 2>&1",
        "nginx": "nginx -v 2>&1",
        "Home dir": "ls -la ~ | head -20",
        "WWW dir": "ls -la ~/www/ 2>/dev/null || echo 'no www'",
        "Disk space": "df -h ~ | tail -1",
        "RAM": "free -m 2>/dev/null | head -3 || echo 'N/A'",
        "Crontab": "crontab -l 2>&1 | head -5",
        "Subdomain dir": "ls -la ~/www/app.agile-business-pro.com/ 2>/dev/null || echo 'no subdir'",
        "PHP": "php -v 2>/dev/null | head -1 || echo 'no php'",
        "Git": "git --version 2>&1",
        "Virtualenv": "which virtualenv 2>&1; which python3 -m venv 2>&1",
    }

    print("=" * 50)
    print("SERVER CAPABILITIES")
    print("=" * 50)
    for label, cmd in commands.items():
        out, err, code = ssh_exec(client, cmd)
        result = (out + err).strip()
        print(f"\n--- {label} ---")
        print(result[:500] if result else "(empty)")

    client.close()
    print("\n\nDone.")

if __name__ == "__main__":
    main()
