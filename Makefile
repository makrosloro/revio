# Makefile — NegocioSano
# Comandos de uso diario para desarrollo y operaciones.
# Uso: make <comando>

.PHONY: help dev test migrate status logs restart-app backup-db \
        feature release hotfix gitflow-init

COMPOSE_LOCAL = docker-compose
COMPOSE_PROD  = docker-compose -f docker-compose.prod.yml
VPS           = deploy@$(shell grep VPS_HOST .vps_host 2>/dev/null || echo "IP_DEL_VPS")

# ── Ayuda ────────────────────────────────────────────────
help:
	@echo ""
	@echo "NegocioSano — Comandos disponibles disponibles"
	@echo "──────────────────────────────────────────────"
	@echo "Desarrollo:"
	@echo "  make dev              Arrancar entorno de desarrollo local"
	@echo "  make test             Ejecutar todos los tests"
	@echo "  make test-cov         Tests con reporte de cobertura"
	@echo "  make lint             Verificar estilo de código"
	@echo ""
	@echo "Base de datos:"
	@echo "  make migrate          Ejecutar migraciones pendientes"
	@echo "  make migration m=txt  Crear nueva migración (m='descripcion')"
	@echo "  make backup-db        Backup manual de la BD"
	@echo ""
	@echo "Operaciones VPS:"
	@echo "  make status           Estado de contenedores en VPS"
	@echo "  make logs             Logs de la app en VPS en tiempo real"
	@echo "  make restart-app      Reiniciar solo la app en VPS"
	@echo "  make deploy           Deploy manual al VPS (solo si CI/CD falla)"
	@echo ""
	@echo "GitFlow:"
	@echo "  make gitflow-init     Inicializar GitFlow en el repo"
	@echo "  make feature f=nombre Iniciar nueva feature"
	@echo "  make release v=X.Y.Z  Iniciar nueva release"
	@echo "  make hotfix h=nombre  Iniciar hotfix de emergencia"
	@echo ""

# ── Desarrollo local ─────────────────────────────────────
dev:
	@echo "Arrancando entorno de desarrollo..."
	docker-compose up -d db
	@sleep 3
	alembic upgrade head
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-report=html
	@echo "Reporte HTML en: htmlcov/index.html"

lint:
	ruff check app/ tests/
	mypy app/ --ignore-missing-imports

# ── Base de datos ─────────────────────────────────────────
migrate:
	@echo "Ejecutando migraciones..."
	alembic upgrade head
	@echo "✅ Migraciones completadas"

migration:
	@if [ -z "$(m)" ]; then echo "Uso: make migration m='descripcion del cambio'"; exit 1; fi
	alembic revision --autogenerate -m "$(m)"
	@echo "✅ Migración creada — revisar el archivo generado antes de aplicar"

backup-db:
	@echo "Creando backup de la BD..."
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	mkdir -p ./backups; \
	docker exec negociosano-db-1 pg_dump -U postgres negociosano \
	  | gzip > "./backups/negociosano_$$TIMESTAMP.sql.gz"; \
	echo "✅ Backup: ./backups/negociosano_$$TIMESTAMP.sql.gz"

# ── Operaciones VPS ──────────────────────────────────────
status:
	ssh $(VPS) "cd /home/deploy/negociosano && $(COMPOSE_PROD) ps"

logs:
	ssh $(VPS) "cd /home/deploy/negociosano && $(COMPOSE_PROD) logs app --tail=100 -f"

restart-app:
	@echo "Reiniciando app en VPS..."
	ssh $(VPS) "cd /home/deploy/negociosano && $(COMPOSE_PROD) restart app"
	@echo "✅ App reiniciada"

deploy:
	@echo "⚠️  Deploy manual al VPS — el CI/CD automático es preferible"
	@git status --short
	@read -p "¿Continuar? [y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
	  ssh $(VPS) "cd /home/deploy/negociosano && \
	    git pull origin main && \
	    $(COMPOSE_PROD) build app && \
	    $(COMPOSE_PROD) up -d app && \
	    sleep 15 && \
	    $(COMPOSE_PROD) exec -T app alembic upgrade head && \
	    curl -f http://localhost:8000/health" && \
	  echo "✅ Deploy completado"; \
	else \
	  echo "Deploy cancelado"; \
	fi

# ── GitFlow ──────────────────────────────────────────────
gitflow-init:
	git flow init -d
	@echo "✅ GitFlow inicializado"
	@echo "Ramas: main (producción) / develop (integración)"

feature:
	@if [ -z "$(f)" ]; then echo "Uso: make feature f=nombre-de-la-feature"; exit 1; fi
	git checkout develop && git pull origin develop
	git flow feature start $(f)
	@echo "✅ Feature '$(f)' iniciada desde develop"
	@echo "Cuando termines: git flow feature finish $(f)"

release:
	@if [ -z "$(v)" ]; then echo "Uso: make release v=1.2.0"; exit 1; fi
	git checkout develop && git pull origin develop
	make test
	@echo "Tests OK — iniciando release v$(v)..."
	git flow release start $(v)
	@echo "✅ Release v$(v) iniciada"
	@echo "1. Actualiza CHANGELOG.md"
	@echo "2. Cuando termines: git flow release finish $(v)"
	@echo "3. Después: git push origin main && git push origin develop && git push origin --tags"

hotfix:
	@if [ -z "$(h)" ]; then echo "Uso: make hotfix h=descripcion-breve"; exit 1; fi
	git checkout main && git pull origin main
	git flow hotfix start $(h)
	@echo "✅ Hotfix '$(h)' iniciado desde main"
	@echo "Cuando termines: git flow hotfix finish $(h)"
	@echo "Después: git push origin main && git push origin develop && git push origin --tags"
