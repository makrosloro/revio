# Makefile — Revio
# Comandos de uso diario para desarrollo y operaciones.
# Uso: make <comando>

.PHONY: help dev test migrate status logs restart-app backup-db \
        feature release hotfix gitflow-init

COMPOSE_NAS = docker-compose -f docker-compose.nas.yml
COMPOSE_SERVER = docker-compose -f docker-compose.server.yml

# ── Ayuda ────────────────────────────────────────────────
help:
	@echo ""
	@echo "Revio — Comandos disponibles"
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
	@echo "Operaciones NAS:"
	@echo "  make status           Estado de todos los contenedores"
	@echo "  make logs             Logs de la app en tiempo real"
	@echo "  make restart-app      Reiniciar solo la app (sin BD)"
	@echo "  make deploy-nas       Deploy manual al NAS"
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
	docker exec revio-db-1 pg_dump -U postgres revio \
	  | gzip > "./backups/revio_$$TIMESTAMP.sql.gz"; \
	echo "✅ Backup: ./backups/revio_$$TIMESTAMP.sql.gz"

# ── Operaciones NAS ──────────────────────────────────────
status:
	$(COMPOSE_NAS) ps

logs:
	$(COMPOSE_NAS) logs app --tail=100 -f

restart-app:
	@echo "Reiniciando app..."
	$(COMPOSE_NAS) restart app
	@sleep 5
	$(COMPOSE_NAS) ps app
	@echo "✅ App reiniciada"

deploy-nas:
	@echo "⚠️  Deploy manual al NAS — asegúrate de estar en rama main"
	@git status --short
	@read -p "¿Continuar? [y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
	  $(COMPOSE_NAS) build app && \
	  $(COMPOSE_NAS) up -d app && \
	  sleep 10 && \
	  $(COMPOSE_NAS) exec app alembic upgrade head && \
	  curl -sf http://localhost:8000/health && \
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
