# Revio — Monitor de Reputación Online

## Qué es
SaaS multi-tenant en Python que monitoriza reseñas de negocios (Google Maps, TripAdvisor, Booking) y gestiona la reputación online completa vía Telegram. Las reseñas negativas (≤3★) generan alerta inmediata con borrador de respuesta. Las positivas (≥4★) se agrupan en un resumen diario. En el plan Multi, el propietario puede publicar respuestas directamente en Google con un botón desde Telegram, vía Google Business Profile API.

## Stack
- **Backend:** FastAPI + Python 3.11
- **Base de datos:** PostgreSQL (snake_case, siempre)
- **Bot:** python-telegram-bot 20.x (API async, no polling legacy)
- **Tareas:** APScheduler (MVP) → Celery + Redis (fase 2)
- **Scraping:** httpx + Playwright (fase 2)
- **IA:** Anthropic Claude API modelo `claude-haiku-4-5` (borradores de respuesta)
- **Pagos:** Stripe (webhooks + Checkout Sessions)
- **Deploy:** Docker Compose + Cloudflare Tunnel (NAS Synology)

## Estructura del proyecto
```
revio/
├── app/
│   ├── main.py              # FastAPI app + arranque del bot
│   ├── config.py            # Settings desde .env (pydantic-settings)
│   ├── database.py          # Engine + SessionLocal + Base
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── repositories/        # Queries de BD (siempre filtradas por user_id)
│   ├── services/            # Lógica de negocio
│   ├── bot/                 # Handlers de Telegram
│   │   ├── middleware.py    # require_subscription decorator
│   │   ├── handlers/        # Un archivo por comando
│   │   └── keyboards.py     # InlineKeyboards reutilizables
│   ├── integrations/
│   │   ├── google_places.py
│   │   ├── google_business_profile.py  # fase 3 — publicación de respuestas
│   │   ├── tripadvisor.py   # fase 2
│   │   ├── stripe_client.py
│   │   └── anthropic_client.py  # fase 2
│   ├── scheduler/
│   │   └── tasks.py         # Polling de reseñas
│   └── webhooks/
│       └── stripe.py        # Endpoint webhook de Stripe
├── alembic/                 # Migraciones
├── tests/
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── requirements.txt
```

## Reglas absolutas
1. **Aislamiento de datos:** toda query que devuelva datos de negocio o reseñas DEBE filtrar por `user_id`. Sin excepción. Usar siempre los métodos del repositorio, nunca queries directas en handlers.
2. **Sin acceso a BD en handlers del bot:** los handlers solo llaman a servicios. Los servicios llaman a repositorios. Los repositorios hablan con la BD.
3. **Variables de entorno:** todo en `.env`, cargado vía `config.py` con pydantic-settings. Sin hardcodear secretos en ningún fichero.
4. **Async everywhere:** FastAPI y python-telegram-bot son async. Ninguna función IO es síncrona.
5. **Migrations con Alembic:** ningún `Base.metadata.create_all()` en producción. Solo Alembic.

## Variables de entorno requeridas
```
TELEGRAM_BOT_TOKEN=
DATABASE_URL=postgresql+asyncpg://...
GOOGLE_PLACES_API_KEY=
GOOGLE_CLIENT_ID=          # fase 3 — Google Business Profile API (OAuth)
GOOGLE_CLIENT_SECRET=      # fase 3 — Google Business Profile API (OAuth)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_MULTI_PRICE_ID=
ANTHROPIC_API_KEY=
CLOUDFLARE_TUNNEL_TOKEN=
DAILY_DIGEST_HOUR=21       # hora de envío del resumen diario de positivas (por defecto 21:00)
```

## Comandos útiles
```bash
# Arrancar en desarrollo
docker-compose up -d db
uvicorn app.main:app --reload

# Migraciones
alembic revision --autogenerate -m "descripcion"
alembic upgrade head

# Tests
pytest tests/ -v

# Bot en desarrollo (webhook local via ngrok o cloudflared)
cloudflared tunnel --url http://localhost:8000
```

## Git y despliegue

- **Repositorio:** GitHub privado. Rama principal `main`, integración en `develop`.
- **Workflow:** GitFlow estricto. Ver `.claude/rules/gitflow.md` y `docs/GITFLOW.md`.
- **Despliegue actual:** NAS Synology (`192.168.1.155` / `kerchack.synology.me`) vía GitHub Actions self-hosted runner.
- **Despliegue futuro:** servidor dedicado vía GitHub Actions + SSH. Ver `docs/DEPLOYMENT_SERVER.md`.
- **CI/CD:** tests automáticos en cada push, deploy automático a NAS en merge a `main`.
- **Documentación:** cada feature, hotfix y release documenta sus cambios en `CHANGELOG.md` siguiendo Keep a Changelog. Commits en Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
- **Docker Compose:** `docker-compose.yml` (base) + `docker-compose.nas.yml` (NAS) + `docker-compose.prod.yml` (servidor futuro).

## Regla de documentación
Cada vez que se completa una tarea significativa (agente, feature, hotfix): actualizar `CHANGELOG.md` en la sección `[Unreleased]` con una línea descriptiva. Los commits deben ser atómicos y descriptivos — un commit por cambio lógico, no commits masivos.

## Repositorio y control de versiones
- **Repositorio:** GitHub privado. Rama principal `main` (producción), integración en `develop`.
- **Workflow:** GitFlow estricto. Ver `GITFLOW.md` para comandos exactos.
- **Commits:** Conventional Commits obligatorio — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- **Documentación:** cada PR debe actualizar `CHANGELOG.md` y cualquier doc de `docs/` afectada.
- **Tags:** toda release lleva tag semántico `vMAJOR.MINOR.PATCH` creado por `git flow release finish`.

## Despliegue
- **Fase actual:** NAS Synology vía runner auto-hospedado de GitHub Actions (Docker en el NAS). Ver `docs/DEPLOYMENT_NAS.md`.
- **Fase futura:** servidor dedicado vía GitHub Actions + SSH. Ver `docs/DEPLOYMENT_SERVER.md`.
- **Migración:** guía paso a paso en `docs/MIGRATION.md`.
- **Entornos:** `develop` → NAS (staging), `main` → NAS (producción) → servidor (producción futura).
- **Secrets de GitHub:** `NAS_SSH_KEY`, `NAS_HOST`, `NAS_USER`, `NAS_PROJECT_PATH` para despliegue en NAS.

## Fases de desarrollo
- **Fase 1 (MVP):** Google Maps + alertas negativas inmediatas + Stripe + auth multi-tenant
- **Fase 2:** TripAdvisor/Booking + alertas positivas con resumen diario + borradores IA (negativos y positivos) + informe PDF semanal
- **Fase 3:** Google Business Profile API — publicación de respuestas directamente en Google con botón inline desde Telegram (solo plan Multi)

## Contexto de negocio
- **Plan Free:** Google Maps únicamente, alertas negativas (≤3★) sin borrador de respuesta
- **Plan Pro (29€/mes):** 3 plataformas, alerta inmediata de negativas + resumen diario de positivas, borradores IA para ambas, informe PDF semanal
- **Plan Multi (59€/mes):** todo lo de Pro + hasta 3 locales + publicación directa en Google vía GBP API con aprobación en Telegram
- **Target:** restaurantes, bares, hoteles, retail independiente en España
- **Bootstrap total:** infraestructura en NAS, 0€ coste fijo hasta 30 clientes
- **Diferenciador clave:** gestión completa de reputación (negativas + positivas) + publicación directa en Google. Ninguna herramienta a 29€/mes hace esto para el pequeño hostelero español
