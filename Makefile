# Stack Deployer — Makefile
# Usage: make <target>

COMPOSE = docker compose -f docker/docker-compose.yml
BACKEND = $(COMPOSE) exec backend

.PHONY: help up down restart logs shell migrate makemigrations lint test setup

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Stack lifecycle ───────────────────────────────────────────────────────────

up: ## Démarre tous les services (build si nécessaire)
	$(COMPOSE) up -d --build

down: ## Arrête et supprime les conteneurs
	$(COMPOSE) down

restart: ## Redémarre tous les services
	$(COMPOSE) restart

rebuild: ## Force rebuild de l'image backend/celery
	$(COMPOSE) build --no-cache backend celery
	$(COMPOSE) up -d

# ── Logs ──────────────────────────────────────────────────────────────────────

logs: ## Affiche les logs de tous les services (follow)
	$(COMPOSE) logs -f

logs-backend: ## Logs du backend uniquement
	$(COMPOSE) logs -f backend

logs-celery: ## Logs du worker Celery uniquement
	$(COMPOSE) logs -f celery

logs-frontend: ## Logs du frontend uniquement
	$(COMPOSE) logs -f frontend

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Applique les migrations Alembic en attente
	$(BACKEND) alembic upgrade head

makemigrations: ## Génère une nouvelle migration Alembic (MSG="description")
	$(BACKEND) alembic revision --autogenerate -m "$(MSG)"

db-shell: ## Ouvre un shell psql sur la base de données
	$(COMPOSE) exec postgres psql -U deployer -d stack_deployer

# ── Dev ───────────────────────────────────────────────────────────────────────

shell: ## Shell bash dans le conteneur backend
	$(BACKEND) bash

shell-celery: ## Shell bash dans le conteneur Celery
	$(COMPOSE) exec celery bash

lint: ## Lint Python avec ruff
	$(BACKEND) ruff check app/

format: ## Formate Python avec ruff
	$(BACKEND) ruff format app/

# ── Setup ─────────────────────────────────────────────────────────────────────

setup: ## Première installation : copie .env.example → .env
	@if [ ! -f backend/.env ]; then \
		cp backend/.env.example backend/.env; \
		echo "✓ backend/.env créé — remplis les valeurs avant de lancer make up"; \
	else \
		echo "backend/.env existe déjà, rien à faire"; \
	fi

check-env: ## Vérifie que les variables critiques sont définies dans .env
	@echo "Vérification de backend/.env..."
	@grep -q "^SECRET_KEY=change-me" backend/.env && \
		echo "⚠ ATTENTION: SECRET_KEY n'a pas été changée !" || true
	@grep -q "^PROXMOX_TOKEN_VALUE=xxx" backend/.env && \
		echo "⚠ ATTENTION: PROXMOX_TOKEN_VALUE n'est pas configuré !" || true
	@grep -q "^FIRST_ADMIN_PASSWORD=change-me" backend/.env && \
		echo "⚠ ATTENTION: FIRST_ADMIN_PASSWORD n'a pas été changée !" || true
	@echo "Vérification terminée."

ansible-deps: ## Installe les collections Ansible Galaxy localement
	ansible-galaxy collection install -r backend/ansible/requirements.yml
