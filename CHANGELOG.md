# Changelog — NegocioSano

Todos los cambios notables del proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionado según [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Added
- Panel de administración v2: acciones CRUD — eliminar y bloquear/desbloquear usuarios, eliminar/pausar/reactivar negocios, eliminar reseñas
- Diseño profesional del panel con KPIs, distribución por plan y estado del sistema
- Rediseño completo de la landing page: hero oscuro con grid, mockup de teléfono, comparativa, secciones refinadas

### Changed
- Reseñas guardadas en su idioma original (`originalText`) en lugar de la traducción automática de Google

### Fixed
### Removed

---

## [0.3.0] — 2026-06-03

### Added
- `/agregar` reescrito: búsqueda por texto en Places API, lista de resultados con botones inline, confirmación de propiedad con declaración ToS
- `GooglePlacesClient.search_by_text()` — búsqueda por texto usando Places API v1 textSearch
- Migración `0005` — campo `self_declared_owner` en tabla `businesses`
- Página `/payment/success` — HTML con pasos de activación post-pago
- Página `/payment/cancel` — HTML con mensaje tranquilizador y contacto

### Changed
### Fixed
### Removed

---

## [0.2.0] — 2026-06-03

### Added
- Agente 05: borradores IA con Claude Haiku — alertas negativas con borrador (Pro/Multi), resumen diario con borradores (máx 5), /responder con regeneración, tono configurable por negocio vía /config
- `app/integrations/anthropic_client.py` — AnthropicClient con generate_negative_draft, generate_positive_draft, generate_draft_on_demand y tracking de tokens
- `app/bot/handlers/responder.py` — /responder con selección de reseña, generación y botones Regenerar/Listo
- Migración `0004` — tone DEFAULT 'cercano' en businesses, draft_type y ai_draft_tokens en alert_logs
- Agente 07: `.dockerignore`, `scripts/backup.sh` con retención 7 días, `DEPLOYMENT_SERVER.md` alineado con flujo SSH real
- CI/CD: `STRIPE_PRO_PRICE_ID` y `STRIPE_MULTI_PRICE_ID` añadidos a env vars de tests en `ci.yml` y `deploy.yml`
- Agente 03: sistema completo de polling de Google Maps, clasificación, alertas inmediatas y resumen diario
- Migración `0003_add_review_type_and_digest_sent_at`
- `app/scheduler/tasks.py` — poll_reviews (cada 2h) y daily_digest (21:00 Madrid)
- Suite de 60 tests con SQLite in-memory (repositorios, servicios, integraciones)
- Endpoint `/payment/success` para redirecció post-Stripe
- `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile` multistage, `Caddyfile`
- CI/CD con GitHub Actions: `ci.yml` y `deploy.yml` (SSH al VPS en push a main)
- Modelos SQLAlchemy: `User`, `Business`, `Review`, `AlertLog` con FKs CASCADE e índices
- Migraciones Alembic 0001–0004
- Bot de Telegram: /start, /activar, /suscribir, /agregar, /config, /pausa, /estado, /resenas, /responder
- Autenticación multi-tenant vía Stripe + token de activación por email

### Fixed
- `fix(email)` — SMTPSenderRefused al enviar email de activación (SMTP_FROM con comillas en la dirección)

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
