# Changelog — NegocioSano

Todos los cambios notables del proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionado según [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Added
- `docker-compose.yml` para desarrollo local (solo PostgreSQL, healthcheck)
- `docker-compose.prod.yml` para producción en VPS (app + bd, red interna, solo localhost:8000)
- `Dockerfile` multistage con stage `deps` cacheado y stage `runtime` con usuario no-root `appuser`
- `Caddyfile` para `api.negociosano.com` con reverse proxy, gzip y logging JSON
- `pyproject.toml` con configuración de ruff, mypy y pytest-asyncio
- CI/CD con GitHub Actions: `ci.yml` (tests en push) y `deploy.yml` (deploy SSH al VPS en push a main)
- GitFlow inicializado con ramas `main` y `develop` publicadas en origin
- Estructura completa de carpetas `app/` con todos los módulos y `__init__.py`
- `app/config.py` — Settings con pydantic-settings leyendo desde `.env`
- `app/database.py` — AsyncEngine, AsyncSessionLocal y Base declarativa
- Modelos SQLAlchemy: `User`, `Business`, `Review`, `AlertLog` con FKs CASCADE e índices
- Migración Alembic `0001_initial_schema` con las 4 tablas
- `app/main.py` — FastAPI con lifespan, endpoint `/health` y router de webhooks
- `app/webhooks/stripe.py` — stub con validación de firma Stripe
- `.env.example` con todas las variables requeridas

- Agente 03: sistema de polling de Google Maps, clasificación de reseñas y alertas/resumen diario
- `app/models/review.py` — campos `review_type` (negative/positive) y `digest_sent_at` + índice compuesto
- Migración Alembic `0003_add_review_type_and_digest_sent_at`
- `app/repositories/review_repo.py` — exists, create, get_undigested_positives, mark_digest_sent, get_recent_negatives
- `app/repositories/business_repo.py` — get_all_active con eager load del User, set_active
- `app/repositories/alert_log_repo.py` — create para registrar alertas enviadas
- `app/repositories/user_repo.py` — get_all_active_subscribers para usuarios Pro/Multi activos
- `app/integrations/google_places.py` — GooglePlacesClient con backoff exponencial en rate limit
- `app/services/review_service.py` — poll_all_businesses (ciclo de polling) y send_daily_digest
- `app/services/places_service.py` — extract_place_id_from_url (cubre URLs directas, paths y goo.gl)
- `app/scheduler/tasks.py` — dos jobs APScheduler: poll_reviews (cada 2h) y daily_digest (21:00 Madrid)
- `app/bot/handlers/resenas.py` — comando /resenas con botones inline para negativas/positivas
- Scheduler integrado en el lifespan de FastAPI

### Changed
- `.gitignore` ampliado con `backups/`, `*.sql.gz` y `.mypy_cache/`

### Fixed
### Removed

---

## [0.1.0] — YYYY-MM-DD

### Added
- Estructura inicial del proyecto (FastAPI + PostgreSQL + python-telegram-bot)
- Sistema de autenticación multi-tenant via Stripe + token de activación
- Polling de reseñas de Google Maps cada 2 horas con clasificación por sentimiento
- Alertas inmediatas para reseñas negativas (≤3★) con borrador de respuesta IA
- Resumen diario a las 21:00 para reseñas positivas (≥4★) con borradores de respuesta
- Dos prompts de IA diferenciados: negativas (desactivar queja) y positivas (reforzar relación)
- Middleware `require_subscription` para control de acceso por plan (Free/Pro/Multi)
- Comandos: /start, /activar, /suscribir, /config, /agregar, /pausa, /reanudar, /estado, /resenas, /responder
- Webhook de Stripe: alta, cancelación, pago fallido
- Publicación directa en Google vía Google Business Profile API con botones inline en Telegram (plan Multi)
- GitFlow configurado con ramas main/develop
- CI/CD con GitHub Actions y runner self-hosted en NAS Synology
- Docker Compose para NAS con Cloudflare Tunnel
- Backup automático diario de PostgreSQL
- Documentación completa en docs/ (arquitectura, despliegues, migración)

---

<!-- 
Guía de versiones:
  PATCH (0.1.X): fix de bug, ajuste menor
  MINOR (0.X.0): nueva funcionalidad (nuevo comando, nueva plataforma)
  MAJOR (X.0.0): cambio que rompe compatibilidad

Tipos de cambio:
  Added      nueva funcionalidad
  Changed    cambio en funcionalidad existente
  Fixed      corrección de bug
  Removed    funcionalidad eliminada
  Security   corrección de vulnerabilidad
-->
