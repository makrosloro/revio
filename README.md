# NegocioSano — Reputación Online para tu Negocio

Bot de Telegram que monitoriza reseñas de negocios en Google Maps, TripAdvisor y Booking.com y gestiona la reputación online completa. Las reseñas negativas (≤3★) generan una alerta inmediata con borrador de respuesta generado por IA. Las positivas (≥4★) se agrupan en un resumen diario para no interrumpir el día a día. En el plan Multi, el propietario puede publicar respuestas directamente en Google con un botón desde Telegram.

**Target:** restaurantes, bares, hoteles y retail independiente en España.
**Modelo:** SaaS multi-tenant · Free / Pro (29€/mes) / Multi (59€/mes).

---

## Inicio rápido (desarrollo local)

### Prerrequisitos
- Python 3.11+
- Docker y Docker Compose
- Git con git-flow (`brew install git-flow-avh` en macOS)

### Setup en 5 pasos

```bash
# 1. Clonar y entrar al proyecto
git clone git@github.com:TU_USUARIO/negociosano.git && cd negociosano

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales (ver docs/DEPLOYMENT_NAS.md para guía completa)

# 4. Arrancar BD y ejecutar migraciones
docker-compose up -d db
sleep 5
alembic upgrade head

# 5. Arrancar la app
uvicorn app.main:app --reload
```

La app queda disponible en `http://localhost:8000`. El bot de Telegram arranca automáticamente si `TELEGRAM_BOT_TOKEN` está configurado.

Para probar webhooks de Stripe en local:
```bash
stripe listen --forward-to localhost:8000/webhook/stripe
```

---

## Estructura del proyecto

```
negociosano/
├── app/
│   ├── main.py              # FastAPI app + lifespan (bot + scheduler)
│   ├── config.py            # Settings desde .env (pydantic-settings)
│   ├── database.py          # AsyncEngine + SessionLocal
│   ├── models/              # SQLAlchemy: User, Business, Review, AlertLog
│   ├── repositories/        # Queries de BD — siempre filtradas por user_id
│   ├── services/            # Lógica de negocio
│   ├── bot/
│   │   ├── middleware.py    # require_subscription decorator
│   │   └── handlers/        # Un archivo por comando de Telegram
│   ├── integrations/        # Google Places, Stripe, Anthropic, Playwright
│   ├── scheduler/           # APScheduler — polling de reseñas
│   └── webhooks/            # Endpoints de Stripe y Telegram
├── tests/
│   └── conftest.py          # Fixtures base (BD SQLite, mocks externos)
├── alembic/                 # Migraciones de BD
├── docs/
│   ├── DEPLOYMENT_NAS.md    # Despliegue en NAS paso a paso
│   ├── DEPLOYMENT_SERVER.md # Despliegue futuro en servidor dedicado
│   └── MIGRATION.md         # Migración NAS → servidor
├── .claude/
│   ├── agents/              # Agentes de Claude Code (00-08)
│   └── rules/               # Convenciones de código
├── .github/
│   └── workflows/
│       ├── ci.yml           # Tests en cada push/PR
│       └── deploy.yml       # Deploy al NAS (runner self-hosted)
├── CLAUDE.md                # Contexto principal para Claude Code
├── GITFLOW.md               # Referencia completa de GitFlow
├── CHANGELOG.md             # Historial de versiones
└── Makefile                 # Comandos de operación — ver: make help
```

---

## Comandos más usados

```bash
make help          # Ver todos los comandos disponibles

make test          # Ejecutar tests
make test-cov      # Tests con reporte de cobertura
make lint          # Verificar estilo de código

make migrate       # Aplicar migraciones pendientes
make migration m="descripcion"  # Crear nueva migración

make status        # Estado de contenedores en NAS
make logs          # Logs de la app en tiempo real
make backup-db     # Backup manual de la BD

make feature f=nombre   # Iniciar nueva feature (GitFlow)
make release v=X.Y.Z    # Iniciar nueva release (GitFlow)
make hotfix h=nombre    # Hotfix de emergencia (GitFlow)
```

---

## Flujo de trabajo (GitFlow)

```
feature/xxx → develop → release/X.Y.Z → main (deploy automático al NAS)
                                    ↑
                             hotfix/xxx (desde main, urgente)
```

Ver `GITFLOW.md` para la referencia completa con todos los comandos.

---

## Variables de entorno

Ver `.env.example` para la lista completa. Las variables mínimas para desarrollo local:

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot de BotFather |
| `DATABASE_URL` | URL de conexión a PostgreSQL |
| `GOOGLE_PLACES_API_KEY` | API key de Google Cloud (Places API) |
| `STRIPE_SECRET_KEY` | Secret key de Stripe (test o live) |
| `STRIPE_WEBHOOK_SECRET` | Signing secret del webhook de Stripe |
| `STRIPE_PRO_PRICE_ID` | Price ID del plan Pro en Stripe |
| `STRIPE_MULTI_PRICE_ID` | Price ID del plan Multi en Stripe |
| `ANTHROPIC_API_KEY` | API key de Anthropic (fase 2) |
| `CLOUDFLARE_TUNNEL_TOKEN` | Token del tunnel (solo NAS/producción) |
| `WEBHOOK_URL` | URL pública donde Telegram envía updates |
| `BOT_ADMIN_CHAT_ID` | Tu Chat ID de Telegram (alertas internas) |

---

## Despliegue

- **NAS Synology (actual):** ver `docs/DEPLOYMENT_NAS.md`
- **Servidor dedicado (futuro):** ver `docs/DEPLOYMENT_SERVER.md`
- **Migración NAS → servidor:** ver `docs/MIGRATION.md`

El deploy a producción es automático al hacer push a `main` via GitFlow (`git flow release finish X.Y.Z`).

---

## Planes y funcionalidades

| Funcionalidad | Free | Pro | Multi |
|---------------|:----:|:---:|:-----:|
| Alertas negativas inmediatas (≤3★) | ✓ | ✓ | ✓ |
| Borrador de respuesta negativa (IA) | — | ✓ | ✓ |
| Resumen diario de positivas (≥4★) | — | ✓ | ✓ |
| Borrador de respuesta positiva (IA) | — | ✓ | ✓ |
| TripAdvisor + Booking | — | ✓ | ✓ |
| Informe PDF semanal | — | ✓ | ✓ |
| Hasta 3 locales | — | — | ✓ |
| Publicación directa en Google (GBP API) | — | — | ✓ |
| Precio | 0€ | 29€/mes | 59€/mes |

---

## Stack técnico

FastAPI · PostgreSQL · python-telegram-bot 20.x · APScheduler · Playwright · Claude API (Haiku) · Stripe · Docker · Cloudflare Tunnel · GitHub Actions · GitFlow
