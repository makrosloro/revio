---
name: infrastructure
description: Usar cuando se necesite crear o modificar la infraestructura base del proyecto — estructura de carpetas, Docker, base de datos, migraciones, configuración inicial.
---

# Agente 01 — Infraestructura base

## Objetivo
Crear el esqueleto completo del proyecto listo para que los demás agentes construyan encima. Al terminar este agente, `docker-compose up` debe levantar PostgreSQL y la app FastAPI sin errores.

## Tareas en orden

### 1. Estructura de carpetas
Crear toda la estructura definida en CLAUDE.md. Cada carpeta debe tener su `__init__.py`. Crear `requirements.txt` con todas las dependencias de la fase 1:
```
fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic
pydantic-settings python-telegram-bot[webhooks] httpx
stripe apscheduler python-dotenv pytest pytest-asyncio
```

### 2. docker-compose.yml
Dos servicios: `db` (postgres:16-alpine, volumen persistente, healthcheck) y `app` (build desde Dockerfile, depende de db healthy, monta `.env`, expone puerto 8000). Incluir `redis` comentado para fase 2.

### 3. Dockerfile
Python 3.11-slim. Instalar dependencias primero (capa cacheada), luego copiar código. No correr como root. Entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

### 4. config.py
Clase `Settings` con pydantic-settings. Cargar desde `.env`. Incluir todos los campos de CLAUDE.md más: `WEBHOOK_URL` (URL pública del bot), `POLLING_INTERVAL_HOURS=2`, `BOT_ADMIN_CHAT_ID` (para alertas internas de downtime).

### 5. database.py
`AsyncEngine` con `create_async_engine`. `AsyncSession` con `async_sessionmaker`. Dependency `get_db` para FastAPI. `Base` declarativa.

### 6. Modelos SQLAlchemy (app/models/)
Cuatro modelos con todos los campos descritos en el plan:
- `User` — users table
- `Business` — businesses table (FK a users, CASCADE delete)
- `Review` — reviews table (FK a businesses, CASCADE delete)
- `AlertLog` — alerts_log table (FK a reviews)

Todos los modelos heredan de `Base`. Timestamps con `server_default=func.now()`.

### 7. Migración inicial
Configurar Alembic para async. Ejecutar `alembic revision --autogenerate -m "initial schema"`. Verificar que el fichero generado contiene las 4 tablas.

### 8. app/main.py
FastAPI app con lifespan (arranca/para el scheduler y el bot). Router incluido para webhooks. Health check en `GET /health` que devuelve `{"status": "ok", "db": "connected"}`.

### 9. .env.example
Copiar todas las variables de CLAUDE.md con valores de ejemplo (nunca reales).

## Verificación
```bash
docker-compose up -d db
alembic upgrade head
# Debe mostrar las 4 tablas creadas sin errores
psql $DATABASE_URL -c "\dt"
uvicorn app.main:app --reload
curl http://localhost:8000/health
# → {"status": "ok", "db": "connected"}
```
