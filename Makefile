# ==============================================================================
# SBP-FMS (Financial Management System) Makefile
# ==============================================================================

SHELL := /bin/bash
PYTHON := uv run python
MANAGE := PYTHONPATH=sbp_fms $(PYTHON) sbp_fms/manage.py
PYTEST := PYTHONPATH=sbp_fms uv run pytest sbp_fms

.PHONY: help install dev migrate makemigrations superuser seed seed-clean shell test test-fast test-cov \
        validate-schema run gunicorn celery celery-beat collectstatic \
        infra-up infra-down infra-logs dev-docker-up dev-docker-down \
        logs logs-app logs-celery logs-nginx logs-infra logs-file \
        deploy deploy-local restart status clean

# ------------------------------------------------------------------------------
# 1. HELP & DISCOVERY
# ------------------------------------------------------------------------------
help:
	@echo "========================================================================"
	@echo " SBP-FMS Backend Management Commands"
	@echo "========================================================================"
	@echo " Setup & Dependencies:"
	@echo "   make install            Sync all dependencies using uv"
	@echo ""
	@echo " Database & Migrations:"
	@echo "   make migrate            Apply database migrations"
	@echo "   make makemigrations     Generate new database migrations"
	@echo "   make superuser          Create a new Django superuser"
	@echo "   make seed               Seed database with comprehensive test data for all apps"
	@echo "   make seed-clean         Clean existing test data and re-seed from scratch"
	@echo ""
	@echo " Development Server & Workers:"
	@echo "   make dev                Run local Django development server (port 8000)"
	@echo "   make gunicorn           Run production Gunicorn server (port 8080)"
	@echo "   make celery             Start Celery worker process"
	@echo "   make celery-beat        Start Celery Beat scheduler process"
	@echo "   make shell              Open Django interactive shell"
	@echo "   make collectstatic      Collect static assets into staticfiles/"
	@echo ""
	@echo " Testing & Quality:"
	@echo "   make test               Run full pytest test suite (SQLite in-memory)"
	@echo "   make test-fast          Run pytest with fail-fast (-x)"
	@echo "   make validate-schema    Validate OpenAPI 3.0 schema generation"
	@echo ""
	@echo " Docker Infrastructure:"
	@echo "   make infra-up           Start Production PostgreSQL 16 (port 5434) & Redis (port 6379)"
	@echo "   make infra-down         Stop Production PostgreSQL & Redis containers"
	@echo "   make infra-logs         View logs from PostgreSQL & Redis containers"
	@echo "   make dev-docker-up      Start Full Local Dev Stack with Docker"
	@echo "   make dev-docker-down    Stop Full Local Dev Stack"
	@echo ""
	@echo " Logging & Monitoring:"
	@echo "   make logs               Stream live logs from all backend services (Django, Celery Worker & Beat)"
	@echo "   make logs-app           Stream Django/Gunicorn application logs"
	@echo "   make logs-celery        Stream Celery background worker & scheduler logs"
	@echo "   make logs-nginx         Stream Nginx access and error logs"
	@echo "   make logs-infra         Stream Docker PostgreSQL (port 5434) and Redis logs"
	@echo "   make logs-file          Tail application log files in ./logs/"
	@echo ""
	@echo " Deployment & Maintenance:"
	@echo "   make deploy             Run full production deployment script"
	@echo "   make restart            Restart all production services (Docker, Django, Celery, Nginx)"
	@echo "   make status             Show status of all production services"
	@echo "   make deploy-local       Execute deploy_production.sh script locally on server"
	@echo "   make clean              Clean up Python bytecode, pytest cache, and artifacts"
	@echo "========================================================================"

# ------------------------------------------------------------------------------
# 2. DEPENDENCY MANAGEMENT
# ------------------------------------------------------------------------------
install:
	@echo "==> Syncing dependencies with uv..."
	uv sync

# ------------------------------------------------------------------------------
# 3. DATABASE & DJANGO MANAGEMENT
# ------------------------------------------------------------------------------
migrate:
	@echo "==> Applying database migrations..."
	$(MANAGE) migrate --noinput

makemigrations:
	@echo "==> Generating database migrations..."
	$(MANAGE) makemigrations

superuser:
	@echo "==> Creating superuser..."
	$(MANAGE) createsuperuser

seed:
	@echo "==> Seeding database with comprehensive test data for all apps..."
	$(MANAGE) seed_database

seed-clean:
	@echo "==> Cleaning previous demo data and re-seeding..."
	$(MANAGE) seed_database --clean

shell:
	@echo "==> Opening Django shell..."
	$(MANAGE) shell

collectstatic:
	@echo "==> Collecting static assets..."
	$(MANAGE) collectstatic --noinput

# ------------------------------------------------------------------------------
# 4. RUNNING APPLICATION SERVICES
# ------------------------------------------------------------------------------
dev:
	@echo "==> Starting local development server at http://127.0.0.1:8000..."
	$(MANAGE) runserver 0.0.0.0:8000

gunicorn:
	@echo "==> Starting Gunicorn application server on 127.0.0.1:8080..."
	cd sbp_fms && uv run gunicorn --workers 4 --threads 2 --bind 127.0.0.1:8080 --timeout 120 config.wsgi:application

celery:
	@echo "==> Starting Celery worker..."
	cd sbp_fms && uv run celery -A config worker --loglevel=INFO

celery-beat:
	@echo "==> Starting Celery Beat scheduler..."
	cd sbp_fms && uv run celery -A config beat --loglevel=INFO

# ------------------------------------------------------------------------------
# 5. TESTING & QUALITY ASSURANCE
# ------------------------------------------------------------------------------
test:
	@echo "==> Running Pytest test suite (in-memory SQLite)..."
	DEBUG=1 \
	SECRET_KEY="ci-test-secret-key-at-least-50-characters-long-sbp-fms-2026" \
	ALLOWED_HOSTS="localhost,127.0.0.1" \
	DATABASE_URL="sqlite://:memory:" \
	$(PYTEST)

test-fast:
	@echo "==> Running Pytest with fail-fast (-x)..."
	DEBUG=1 \
	SECRET_KEY="ci-test-secret-key-at-least-50-characters-long-sbp-fms-2026" \
	ALLOWED_HOSTS="localhost,127.0.0.1" \
	DATABASE_URL="sqlite://:memory:" \
	$(PYTEST) -x

validate-schema:
	@echo "==> Validating OpenAPI 3.0 Spectacular schema..."
	DEBUG=1 \
	SECRET_KEY="ci-test-secret-key-at-least-50-characters-long-sbp-fms-2026" \
	$(MANAGE) spectacular --file sbp_fms/schema.yml --validate

# ------------------------------------------------------------------------------
# 6. DOCKER INFRASTRUCTURE
# ------------------------------------------------------------------------------
infra-up:
	@echo "==> Starting Production Docker PostgreSQL (port 5434) and Redis..."
	docker compose -f docker-compose.prod.yml up -d --remove-orphans

infra-down:
	@echo "==> Stopping Production Docker containers..."
	docker compose -f docker-compose.prod.yml down

infra-logs:
	docker compose -f docker-compose.prod.yml logs -f

dev-docker-up:
	@echo "==> Starting full development Docker stack..."
	cd sbp_fms && docker compose up -d --build

dev-docker-down:
	@echo "==> Stopping development Docker stack..."
	cd sbp_fms && docker compose down

# ------------------------------------------------------------------------------
# 7. LOGGING & MONITORING
# ------------------------------------------------------------------------------
logs:
	@echo "==> Streaming live logs from all SBP-FMS systemd services (Ctrl+C to exit)..."
	@if command -v journalctl &>/dev/null && systemctl is-active --quiet sbp-fms 2>/dev/null; then \
		journalctl -u sbp-fms -u sbp-fms-celery -u sbp-fms-celery-beat -f --no-hostname -o short-iso; \
	elif [ -d logs ] && ls logs/*.log &>/dev/null; then \
		tail -f -n 50 logs/*.log; \
	else \
		docker compose -f docker-compose.prod.yml logs -f; \
	fi

logs-app:
	@echo "==> Streaming Django Gunicorn application logs..."
	@if command -v journalctl &>/dev/null && systemctl is-active --quiet sbp-fms 2>/dev/null; then \
		journalctl -u sbp-fms -f -n 100 --no-hostname -o short-iso; \
	elif [ -f logs/gunicorn_error.log ]; then \
		tail -f -n 100 logs/gunicorn_error.log logs/gunicorn_access.log; \
	else \
		echo "No Gunicorn systemd service or local log files found."; \
	fi

logs-celery:
	@echo "==> Streaming Celery worker & beat scheduler logs..."
	@if command -v journalctl &>/dev/null && systemctl is-active --quiet sbp-fms-celery 2>/dev/null; then \
		journalctl -u sbp-fms-celery -u sbp-fms-celery-beat -f -n 100 --no-hostname -o short-iso; \
	elif [ -f logs/celery_worker.log ]; then \
		tail -f -n 100 logs/celery_worker.log logs/celery_beat.log; \
	else \
		echo "No Celery systemd service or local log files found."; \
	fi

logs-nginx:
	@echo "==> Streaming Nginx access & error logs..."
	@if [ -f /var/log/nginx/access.log ]; then \
		sudo tail -f -n 100 /var/log/nginx/access.log /var/log/nginx/error.log; \
	else \
		echo "Nginx log directory /var/log/nginx/ not found on this machine."; \
	fi

logs-infra: infra-logs

logs-file:
	@echo "==> Streaming application file logs in logs/ directory..."
	@mkdir -p logs
	@touch logs/gunicorn_access.log logs/gunicorn_error.log logs/celery_worker.log logs/celery_beat.log
	tail -f -n 50 logs/*.log

# ------------------------------------------------------------------------------
# 8. DEPLOYMENT & MAINTENANCE
# ------------------------------------------------------------------------------
deploy: deploy-local

deploy-local:
	@echo "==> Running production deployment script..."
	bash deploy/scripts/deploy_production.sh

restart:
	@echo "==> Restarting all SBP-FMS production services..."
	@if [ -f "docker-compose.prod.yml" ] && command -v docker &> /dev/null; then \
		docker compose -f docker-compose.prod.yml up -d --remove-orphans; \
	fi
	@if command -v systemctl &> /dev/null; then \
		sudo systemctl daemon-reload; \
		sudo systemctl restart sbp-fms sbp-fms-celery sbp-fms-celery-beat; \
		sudo nginx -t && sudo systemctl reload nginx; \
		echo "[+] All production services restarted successfully."; \
	fi

status:
	@echo "=========================================================="
	@echo " SBP-FMS Production Services Status"
	@echo "=========================================================="
	@if command -v systemctl &> /dev/null; then \
		systemctl status sbp-fms --no-pager -l || true; \
		echo "----------------------------------------------------------"; \
		systemctl status sbp-fms-celery --no-pager -l || true; \
		echo "----------------------------------------------------------"; \
		systemctl status sbp-fms-celery-beat --no-pager -l || true; \
		echo "----------------------------------------------------------"; \
		systemctl status nginx --no-pager -l || true; \
	fi
	@if [ -f "docker-compose.prod.yml" ] && command -v docker &> /dev/null; then \
		echo "----------------------------------------------------------"; \
		echo "Docker Containers:"; \
		docker compose -f docker-compose.prod.yml ps; \
	fi

clean:
	@echo "==> Cleaning cache and temporary files..."
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov .tox .nox 2>/dev/null || true
	@echo "[+] Cleaned successfully."
