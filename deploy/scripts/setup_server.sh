#!/usr/bin/env bash
# ==============================================================================
# SBP-FMS One-Click Production Server Setup Script
# Target: Ubuntu / Debian (Nginx + Systemd + SSL + Logging)
# Run as: sudo bash deploy/scripts/setup_server.sh
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo " Starting SBP-FMS Production Deployment Setup..."
echo " Domain: fms.sbpafrica.group"
echo " Internal Port: 127.0.0.1:8080"
echo "=========================================================="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo: sudo bash deploy/scripts/setup_server.sh"
  exit 1
fi

PROJECT_DIR="/home/sbpafrica/sbp_fms_django_backend"
USER_NAME="sbpafrica"
REPO_URL="https://github.com/sbpafrica/account_software_backend.git"

# 1. Clone repository if not already present
if [ ! -d "$PROJECT_DIR/.git" ]; then
  echo "[1/7] Repository not detected at $PROJECT_DIR. Cloning from $REPO_URL..."
  if [ -d "$PROJECT_DIR" ]; then
    rm -rf "$PROJECT_DIR"
  fi
  sudo -u "$USER_NAME" git clone "$REPO_URL" "$PROJECT_DIR"
fi

# 2. Create logs directory
echo "[2/7] Creating application logging directories..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/sbp_fms/staticfiles"
mkdir -p "$PROJECT_DIR/sbp_fms/media"
chown -R "$USER_NAME:$USER_NAME" "$PROJECT_DIR"

# Ensure .env file exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
  if [ -f "$PROJECT_DIR/.env.production" ]; then
    echo "[!] .env not found. Copying .env.production to .env..."
    sudo -u "$USER_NAME" cp "$PROJECT_DIR/.env.production" "$PROJECT_DIR/.env"
  elif [ -f "$PROJECT_DIR/.env.example" ]; then
    echo "[!] .env not found. Copying .env.example to .env..."
    sudo -u "$USER_NAME" cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  fi
fi

# Start Docker PostgreSQL & Redis infrastructure containers
echo "[3/8] Starting Docker PostgreSQL and Redis containers..."
if command -v docker &> /dev/null && [ -f "$PROJECT_DIR/docker-compose.prod.yml" ]; then
  cd "$PROJECT_DIR"
  docker compose -f docker-compose.prod.yml up -d
  echo "[+] Docker PostgreSQL & Redis are running."
  # Wait for postgres to be healthy
  sleep 4
fi

# 3. Configure Nginx
echo "[3/7] Installing Nginx virtual host for fms.sbpafrica.group..."
cp "$PROJECT_DIR/deploy/nginx/fms.sbpafrica.group.conf" /etc/nginx/sites-available/fms.sbpafrica.group.conf

# Enable site if not already enabled
if [ ! -L /etc/nginx/sites-enabled/fms.sbpafrica.group.conf ]; then
  ln -s /etc/nginx/sites-available/fms.sbpafrica.group.conf /etc/nginx/sites-enabled/
fi

# Test Nginx syntax
echo "[3/6] Testing Nginx configuration..."
nginx -t

# Reload Nginx
systemctl reload nginx

# 4. Install Systemd Services
echo "[4/6] Installing Systemd service units (Gunicorn, Celery Worker, Celery Beat)..."
cp "$PROJECT_DIR/deploy/systemd/sbp-fms.service" /etc/systemd/system/sbp-fms.service
cp "$PROJECT_DIR/deploy/systemd/sbp-fms-celery.service" /etc/systemd/system/sbp-fms-celery.service
cp "$PROJECT_DIR/deploy/systemd/sbp-fms-celery-beat.service" /etc/systemd/system/sbp-fms-celery-beat.service

systemctl daemon-reload

# 5. Enable & Start Services
echo "[5/6] Enabling and starting background services..."
systemctl enable sbp-fms.service sbp-fms-celery.service sbp-fms-celery-beat.service
systemctl restart sbp-fms.service sbp-fms-celery.service sbp-fms-celery-beat.service

# 6. Check Service Statuses
echo "[6/6] Verifying service statuses..."
systemctl is-active --quiet sbp-fms.service && echo "[+] sbp-fms (Gunicorn on 8080): ACTIVE" || echo "[-] sbp-fms: FAILED"
systemctl is-active --quiet sbp-fms-celery.service && echo "[+] sbp-fms-celery (Worker): ACTIVE" || echo "[-] sbp-fms-celery: FAILED"
systemctl is-active --quiet sbp-fms-celery-beat.service && echo "[+] sbp-fms-celery-beat (Scheduler): ACTIVE" || echo "[-] sbp-fms-celery-beat: FAILED"

echo "=========================================================="
echo " Setup complete! Next step: Generate SSL certificate:"
echo "   sudo certbot --nginx -d fms.sbpafrica.group"
echo "=========================================================="
