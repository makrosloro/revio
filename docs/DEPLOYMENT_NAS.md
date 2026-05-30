# Despliegue en NAS Synology — Guía Completa

## Arquitectura actual

```
GitHub (código) ──push a main──► GitHub Actions Runner (Docker en NAS)
                                         │
                                         ▼
                                   NAS Synology
                                   ├── Docker: revio_app (FastAPI + Bot)
                                   ├── Docker: revio_db (PostgreSQL)
                                   ├── Docker: github-runner (runner de CI/CD)
                                   └── Cloudflare Tunnel → internet público
```

El runner de GitHub Actions corre **en el propio NAS** como contenedor Docker. Se conecta a GitHub de forma saliente (no necesita puerto abierto). Cuando se hace push a `main`, el runner ejecuta el script de despliegue localmente en el NAS.

---

## Preparación del NAS (una sola vez)

### 1. Estructura de carpetas en el NAS

```bash
ssh TU_USUARIO@192.168.1.155

mkdir -p /volume1/docker/revio
cd /volume1/docker/revio
git clone git@github.com:TU_USUARIO/revio.git .
git log --oneline -5
```

### 2. Archivo .env en el NAS

```bash
# NUNCA subir .env a GitHub — configurar manualmente en el NAS
cp .env.example .env
nano .env
chmod 600 .env
```

Rellenar todos los valores. El `DATABASE_URL` debe apuntar al servicio `db` interno:
`postgresql+asyncpg://postgres:PASSWORD@db:5432/revio`

### 3. Docker Compose para NAS (docker-compose.nas.yml)

Tres servicios: `db` (PostgreSQL con healthcheck y volumen persistente), `app` (FastAPI + bot, depende de db healthy), `tunnel` (Cloudflare, expone la app sin abrir puertos). La app NO expone puertos al host — todo el tráfico entra por el tunnel.

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: revio
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks: [internal]

  app:
    build: .
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    env_file: .env
    volumes:
      - ./logs:/app/logs
    networks: [internal, cloudflare]

  tunnel:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    networks: [cloudflare]

volumes:
  postgres_data:

networks:
  internal:
  cloudflare:
```

### 4. Primer arranque manual

```bash
cd /volume1/docker/revio

# Build inicial
docker-compose -f docker-compose.nas.yml build

# Arrancar BD y esperar healthcheck
docker-compose -f docker-compose.nas.yml up -d db
sleep 15

# Migraciones iniciales
docker-compose -f docker-compose.nas.yml run --rm app alembic upgrade head

# Arrancar todo
docker-compose -f docker-compose.nas.yml up -d

# Verificar
docker-compose -f docker-compose.nas.yml ps
docker-compose -f docker-compose.nas.yml logs app --tail=50
```

### 5. Runner de GitHub Actions en el NAS

```bash
# En GitHub → repo → Settings → Actions → Runners → New self-hosted runner
# Copiar el RUNNER_TOKEN que aparece (válido 1 hora)

docker run -d \
  --name github-runner \
  --restart unless-stopped \
  -e REPO_URL="https://github.com/TU_USUARIO/revio" \
  -e RUNNER_TOKEN="TOKEN_DE_REGISTRO" \
  -e RUNNER_NAME="nas-runner" \
  -e RUNNER_WORKDIR="/tmp/runner/work" \
  -e LABELS="nas,self-hosted,linux" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /volume1/docker/revio:/volume1/docker/revio \
  myoung34/github-runner:latest

# Verificar: GitHub → Settings → Actions → Runners
# Debe aparecer "nas-runner" con estado "Idle" en verde
```

---

## Flujo de despliegue automático

```
git push origin main (via GitFlow release finish)
    │
    ▼
GitHub Actions: job "test" en runner Ubuntu (GitHub-hosted)
    → pytest tests/ — si falla: notificación, STOP
    │
    ▼ (solo si tests pasan)
GitHub Actions: job "deploy" en runner "nas-runner" (self-hosted en NAS)
    → cd /volume1/docker/revio
    → git pull origin main
    → docker-compose -f docker-compose.nas.yml build app
    → docker-compose -f docker-compose.nas.yml up -d app
    → docker-compose run --rm app alembic upgrade head
    → Mensaje Telegram al admin: "✅ Deploy vX.Y.Z completado"
```

---

## Comandos de operación diaria

```bash
# Ver estado
make status

# Ver logs en tiempo real
make logs

# Ejecutar migraciones manualmente
make migrate

# Reiniciar solo la app
make restart-app

# Backup manual de la BD
make backup-db

# Rollback a versión anterior
git checkout vX.Y.Z
docker-compose -f docker-compose.nas.yml build app
docker-compose -f docker-compose.nas.yml up -d app
```

---

## Backup automático de BD

Configurar en Synology Task Scheduler → Create → Scheduled Task → User-defined script:

```bash
#!/bin/bash
# Ejecutar cada día a las 3:00 AM
BACKUP_DIR="/volume1/backups/revio"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
docker exec revio-db-1 pg_dump -U postgres revio \
  | gzip > "$BACKUP_DIR/revio_$DATE.sql.gz"
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

---

## Monitorización básica

```bash
# Añadir al cron del NAS — comprueba cada 5 minutos
*/5 * * * * curl -sf http://localhost:8000/health || \
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d "chat_id=${ADMIN_CHAT_ID}&text=⚠️+Revio+caído"
```
