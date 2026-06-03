---
name: devops
description: Usar para configurar o modificar toda la infraestructura de CI/CD, GitFlow, Docker Compose y documentación de despliegue. Ejecutar este agente PRIMERO si el repositorio es nuevo — antes que cualquier agente de código.
---

# Agente 07 — DevOps, CI/CD y GitFlow

## Prerequisito
Agente 00 completado: VPS provisionado, Caddy activo, DNS configurado, GitHub Secrets añadidos, .env en el VPS.

## Objetivo
Dejar el proyecto con GitFlow inicializado, Docker Compose listo para producción en el VPS, y CI/CD funcional: cada push a `main` lanza tests automáticos y si pasan despliega al VPS via SSH.

---

## Tareas en orden

### 1. Archivos Docker Compose

Crear **dos** ficheros únicamente (no hay NAS):

**`docker-compose.yml`** — desarrollo local (solo PostgreSQL):
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: negociosano
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      retries: 5
volumes:
  postgres_data:
```

**`docker-compose.prod.yml`** — producción en el VPS:
```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: negociosano
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      retries: 5
    networks: [internal]

  app:
    build: .
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    env_file: .env
    ports:
      - "127.0.0.1:8000:8000"    # solo localhost — Caddy hace el proxy
    volumes:
      - ./logs:/app/logs
    networks: [internal]

volumes:
  postgres_data:

networks:
  internal:
    driver: bridge
```

### 2. Caddyfile

Crear en la raíz del proyecto (se copia al VPS durante el deploy):
```
api.negociosano.com {
    reverse_proxy localhost:8000
    encode gzip
    log {
        output file /var/log/caddy/access.log
        format json
    }
}
```

### 3. Dockerfile multistage

Stage `deps` instala dependencias (capa cacheada). Stage `runtime` copia código, crea usuario no-root `appuser`, expone 8000, healthcheck con curl.

```dockerfile
FROM python:3.11-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
RUN useradd -m -u 1000 appuser
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. Archivos de configuración

**.gitignore:**
```
.env
__pycache__/
*.pyc
.pytest_cache/
htmlcov/
*.egg-info/
dist/
.mypy_cache/
logs/
backups/
*.sql.gz
.DS_Store
```

**pyproject.toml:**
```toml
[tool.ruff]
select = ["E", "W", "F", "I", "UP"]
line-length = 100
target-version = "py311"

[tool.mypy]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = ["ignore::DeprecationWarning"]
```

### 5. Inicializar GitFlow

```bash
git flow init -d
git push -u origin main
git push -u origin develop
```

Verificar en GitHub que ambas ramas existen y `develop` es la rama por defecto para PRs.

### 6. GitHub Secrets — verificar que existen

En GitHub → repo → Settings → Secrets → Actions, confirmar que están todos los del agente 00:
- `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PROJECT_PATH`
- `TELEGRAM_BOT_TOKEN`, `BOT_ADMIN_CHAT_ID`

### 7. Protección de ramas en GitHub

Settings → Branches → Add branch ruleset:
- `main`: require status checks (job `test` de ci.yml), no direct push
- `develop`: require status checks (job `test` de ci.yml), no direct push

### 8. Primer deploy al VPS

```bash
# Desde tu máquina local
ssh deploy@IP_DEL_VPS

# En el VPS: clonar el repo y lanzar por primera vez
cd /home/deploy/negociosano
git clone git@github.com:TU_USUARIO/negociosano.git .
docker-compose -f docker-compose.prod.yml up -d db
sleep 15
docker-compose -f docker-compose.prod.yml run --rm app alembic upgrade head
docker-compose -f docker-compose.prod.yml up -d

# Copiar Caddyfile y recargar Caddy
sudo cp Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### 9. Verificar flujo completo de GitFlow + CI/CD

```bash
# En tu máquina local
make feature f=test-setup
echo "# NegocioSano" > README.md
git add . && git commit -m "chore: verificar flujo completo de CI/CD"
git flow feature finish test-setup
git push origin develop
# → GitHub Actions debe ejecutar CI (tests)
# Abrir PR develop → main en GitHub → merge → push a main
# → GitHub Actions debe ejecutar CI + deploy al VPS
```

## Verificación final

```bash
# CI pasa en cada push a develop
# GitHub Actions: job 'test' verde en ci.yml

# Deploy automático al hacer push a main
# GitHub Actions: job 'deploy' verde en deploy.yml

# App corriendo en el VPS
curl https://api.negociosano.com/health
# → {"status": "ok", "db": "connected"}

# Bot de Telegram responde
# Enviar /start a @NegocioSanoBot → debe responder
```
