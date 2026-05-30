# Despliegue en Servidor Dedicado — Guía Completa

> Activar esta guía cuando el MRR justifique el coste del servidor (~50+ clientes).
> Coste estimado: 20-40€/mes en Hetzner o Contabo (4 vCPU, 8GB RAM, 80GB SSD).

## Arquitectura objetivo

```
GitHub (código)
    │
    ├── push a develop → CI (tests) → ❌ o ✅ sin deploy
    │
    └── push a main (vía GitFlow) → CI + CD
                    │
                    ▼
         GitHub Container Registry (GHCR)
         ghcr.io/TU_USUARIO/revio:vX.Y.Z
                    │
             SSH deploy al servidor
                    │
                    ▼
         Servidor dedicado Ubuntu 24.04
         ├── Caddy (reverse proxy + TLS automático)
         ├── Docker: revio_app
         ├── Docker: revio_db (PostgreSQL)
         └── Docker: redis (Celery — fase 2)
```

---

## Preparación del servidor (una sola vez)

### 1. Provisioning inicial

```bash
ssh root@IP_SERVIDOR

apt update && apt upgrade -y
apt install -y docker.io docker-compose-plugin git curl ufw fail2ban

# Firewall mínimo
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Usuario de deploy sin root
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
```

### 2. SSH key para GitHub Actions

```bash
# En tu máquina local
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/revio_deploy

# Clave PÚBLICA → pegar en authorized_keys del servidor
cat ~/.ssh/revio_deploy.pub
# En servidor: echo "CLAVE_PUBLICA" >> /home/deploy/.ssh/authorized_keys

# Clave PRIVADA → GitHub → Settings → Secrets → Actions → New secret
# Name: SERVER_SSH_KEY / Value: contenido de la clave privada
cat ~/.ssh/revio_deploy
```

### 3. Secrets de GitHub requeridos

```
SERVER_HOST          → IP o dominio del servidor
SERVER_USER          → deploy
SERVER_SSH_KEY       → clave privada Ed25519
SERVER_PROJECT_PATH  → /home/deploy/revio
GHCR_TOKEN           → GitHub PAT con permisos packages:write
```

### 4. Caddy como reverse proxy

```bash
# Instalar Caddy en el servidor
apt install -y debian-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# /etc/caddy/Caddyfile
# TU_DOMINIO.com {
#     reverse_proxy localhost:8000
#     encode gzip
# }

systemctl enable caddy && systemctl start caddy
```

### 5. Docker Compose para servidor (docker-compose.server.yml)

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
      retries: 5
    networks: [internal]

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks: [internal]

  app:
    image: ghcr.io/TU_USUARIO/revio:${APP_VERSION:-latest}
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    env_file: .env
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./logs:/app/logs
    networks: [internal]

  worker:
    image: ghcr.io/TU_USUARIO/revio:${APP_VERSION:-latest}
    restart: unless-stopped
    command: celery -A app.worker worker --loglevel=info
    depends_on: [db, redis]
    env_file: .env
    networks: [internal]

volumes:
  postgres_data:
networks:
  internal:
```

---

## Flujo de deploy automático

```
git flow release finish X.Y.Z
git push origin main && git push origin --tags
    │
    ▼ GitHub Actions: ci.yml (tests)
    │   └─ FALLA → STOP, email de notificación
    │
    └─ OK ▼ GitHub Actions: deploy.yml
        → docker build + push a GHCR con tag vX.Y.Z
        → SSH al servidor
        → docker-compose pull app worker
        → docker-compose up -d app worker
        → alembic upgrade head
        → curl health check
        → Telegram al admin: "✅ vX.Y.Z desplegado en servidor"
```

---

## Backup automático

```bash
#!/bin/bash
# /home/deploy/scripts/backup.sh — cron diario 3:00 AM
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/deploy/revio/backups"

docker exec revio-db-1 pg_dump -U postgres revio \
  | gzip > "$BACKUP_DIR/revio_$DATE.sql.gz"

# Opcional: sincronizar a almacenamiento externo
# rclone copy "$BACKUP_DIR/revio_$DATE.sql.gz" b2:revio-backups/

find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

---

## Rollback rápido

```bash
ssh deploy@IP_SERVIDOR
cd /home/deploy/revio

# Rollback a versión anterior
export APP_VERSION=v1.1.0
docker-compose -f docker-compose.server.yml pull app worker
docker-compose -f docker-compose.server.yml up -d app worker

# Si hay que revertir migración de BD
docker-compose -f docker-compose.server.yml exec app alembic downgrade -1
```
