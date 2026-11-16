#!/usr/bin/env bash
# ==============================================================================
# SBP-FMS Production Deployment Script (Executed on Remote Server)
# Target: Ubuntu / Debian
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo " Starting SBP-FMS Production Update on $(hostname)..."
echo " Time: $(date)"
echo " Working Directory: $(pwd)"
echo " Running as user: $(whoami)"
echo "=========================================================="

export PATH="$HOME/.local/bin:$PATH:/usr/local/bin:/usr/bin:/bin"
PROJECT_DIR="/home/sbpafrica/sbp_fms_django_backend"

cd "$PROJECT_DIR"

# 1. Ensure .env exists
if [ ! -f ".env" ]; then
  if [ -f ".env.production" ]; then
    echo "[+] Creating .env from .env.production..."
    cp .env.production .env
  elif [ -f ".env.example" ]; then
    echo "[+] Creating .env from .env.example..."
    cp .env.example .env
  fi
fi

# 2. Ensure Docker PostgreSQL and Redis are running
if [ -f "docker-compose.prod.yml" ] && command -v docker &> /dev/null; then
  echo "[+] Ensuring PostgreSQL & Redis Docker infrastructure is up..."
  # Remove any legacy standalone or conflicting containers
  docker rm -f sbp_fms_redis sbp_fms_db 2>/dev/null || true
  docker compose -f docker-compose.prod.yml up -d --remove-orphans
  sleep 4
fi

# 3. Ensure uv package manager is installed
if ! command -v uv &> /dev/null; then
  echo "[+] Installing Astral uv package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
fi

# 4. Sync Python virtual environment dependencies
echo "[+] Syncing Python dependencies with uv..."
uv sync --frozen || uv sync

# 5. Run database migrations
echo "[+] Running Django database migrations..."
PYTHONPATH=sbp_fms uv run python sbp_fms/manage.py migrate --noinput

# 6. Collect static assets
echo "[+] Collecting static assets for Nginx..."
PYTHONPATH=sbp_fms uv run python sbp_fms/manage.py collectstatic --noinput

# 7. First-time setup or reload Systemd & Nginx
if [ ! -f "/etc/systemd/system/sbp-fms.service" ]; then
  echo "[!] First-time setup detected. Executing deploy/scripts/setup_server.sh..."
  if [ -n "${SSH_PASSWORD:-}" ]; then
    echo "$SSH_PASSWORD" | sudo -S bash deploy/scripts/setup_server.sh
  else
    sudo bash deploy/scripts/setup_server.sh
  fi
else
  echo "[+] Updating Systemd service definitions & Nginx virtual host..."
  if [ -n "${SSH_PASSWORD:-}" ]; then
    echo "$SSH_PASSWORD" | sudo -S cp deploy/systemd/sbp-fms*.service /etc/systemd/system/
    echo "$SSH_PASSWORD" | sudo -S cp deploy/nginx/fms.sbpafrica.group.conf /etc/nginx/sites-available/
    echo "$SSH_PASSWORD" | sudo -S systemctl daemon-reload
    echo "$SSH_PASSWORD" | sudo -S systemctl restart sbp-fms sbp-fms-celery sbp-fms-celery-beat
    echo "$SSH_PASSWORD" | sudo -S nginx -t && echo "$SSH_PASSWORD" | sudo -S systemctl reload nginx
  else
    sudo cp deploy/systemd/sbp-fms*.service /etc/systemd/system/
    sudo cp deploy/nginx/fms.sbpafrica.group.conf /etc/nginx/sites-available/
    sudo systemctl daemon-reload
    sudo systemctl restart sbp-fms sbp-fms-celery sbp-fms-celery-beat
    sudo nginx -t && sudo systemctl reload nginx
  fi
fi

echo "=========================================================="
echo " SBP-FMS Deployment Completed Successfully at $(date)!"
echo "=========================================================="
