# Despliegue en VPS Hetzner Cloud — Guía Completa

> VPS Hetzner CX22 (2 vCPU, 4 GB RAM, 40 GB SSD, ~4,35€/mes).
> Dominio negociosano.com gestionado en Cloudflare.

## Arquitectura

```
GitHub (código)
    │
    ├── push a develop / feature/* → CI (tests + migraciones)
    │                                → ❌ o ✅  sin deploy
    │
    └── push a main (vía GitFlow release) → CI + CD
                    │
                    ▼
         GitHub Actions (ubuntu-latest)
         └── SSH al VPS
                    │
                    ▼
         VPS Hetzner Ubuntu 24.04
         ├── Caddy  — reverse proxy + TLS automático
         └── Docker Compose (docker-compose.prod.yml)
             ├── negociosano-db-1   (PostgreSQL 16)
             └── negociosano-app-1  (FastAPI + bot)
```

---

## 1. Provisioning inicial del VPS (una sola vez)

```bash
ssh root@IP_DEL_VPS

# Actualizar sistema
apt update && apt upgrade -y
apt install -y docker.io docker-compose-plugin git curl ufw fail2ban

# Firewall mínimo
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Usuario de deploy (sin permisos root)
useradd -m -s /bin/bash deploy
usermod -aG docker deploy

# Crear carpetas de trabajo
mkdir -p /home/deploy/negociosano/logs /home/deploy/negociosano/backups
chown -R deploy:deploy /home/deploy/negociosano
```

---

## 2. SSH key para GitHub Actions

```bash
# En tu máquina local — genera clave dedicada para CI
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/negociosano_deploy

# Copia la clave PÚBLICA al VPS
ssh-copy-id -i ~/.ssh/negociosano_deploy.pub deploy@IP_DEL_VPS
# o manualmente:
# cat ~/.ssh/negociosano_deploy.pub >> /home/deploy/.ssh/authorized_keys

# La clave PRIVADA va como GitHub Secret (ver sección 3)
cat ~/.ssh/negociosano_deploy
```

---

## 3. GitHub Secrets requeridos

Ir a: GitHub repo → Settings → Secrets and variables → Actions

| Secret | Valor |
|--------|-------|
| `VPS_HOST` | IP o dominio del VPS |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Contenido completo de `~/.ssh/negociosano_deploy` (clave privada) |
| `VPS_PROJECT_PATH` | `/home/deploy/negociosano` |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `BOT_ADMIN_CHAT_ID` | Tu Telegram user ID numérico |

---

## 4. Caddy como reverse proxy con TLS automático

```bash
# Instalar Caddy en el VPS
apt install -y debian-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Copiar Caddyfile del repo
cp /home/deploy/negociosano/Caddyfile /etc/caddy/Caddyfile
systemctl enable caddy && systemctl restart caddy
```

El `Caddyfile` del repo (raíz del proyecto) configura TLS automático vía Let's Encrypt para `api.negociosano.com`.

---

## 5. Primer deploy manual (una sola vez)

```bash
ssh deploy@IP_DEL_VPS
cd /home/deploy/negociosano

# Clonar el repo
git clone git@github.com:TU_USUARIO/negociosano.git .

# Crear .env de producción a partir del ejemplo
cp .env.example .env
nano .env  # completar todos los valores reales

# Arrancar la BD primero
docker compose -f docker-compose.prod.yml up -d db
sleep 15

# Ejecutar migraciones
docker compose -f docker-compose.prod.yml run --rm app alembic upgrade head

# Arrancar la app
docker compose -f docker-compose.prod.yml up -d

# Verificar
curl http://localhost:8000/health
# → {"status": "ok", "db": "connected"}

# Recargar Caddy con el nuevo Caddyfile
sudo cp Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy

# Verificar TLS (puede tardar 1-2 min para que Let's Encrypt emita el certificado)
curl https://api.negociosano.com/health
# → {"status": "ok", "db": "connected"}
```

---

## 6. Flujo automático de CI/CD

```
git flow release finish X.Y.Z
git push origin main && git push origin develop && git push origin --tags
    │
    ▼ GitHub Actions: deploy.yml (job test)
    │   ├── Instala dependencias Python
    │   ├── alembic upgrade head (PostgreSQL de CI)
    │   ├── pytest tests/ -v
    │   └── FALLA → STOP + notificación Telegram al admin
    │
    └── OK ▼ GitHub Actions: deploy.yml (job deploy)
        ├── SSH al VPS
        ├── git pull origin main
        ├── docker compose build app
        ├── docker compose up -d app
        ├── sleep 15
        ├── alembic upgrade head (BD de producción)
        ├── curl health check
        └── Notificación Telegram: "✅ vX.Y.Z desplegado"
```

---

## 7. Backup automático de la BD

Configurar cron job en el VPS como usuario `deploy`:

```bash
crontab -e
# Añadir:
0 3 * * * /home/deploy/negociosano/scripts/backup.sh >> /home/deploy/negociosano/logs/backup.log 2>&1
```

El script `scripts/backup.sh` hace pg_dump comprimido y elimina backups con más de 7 días. Los backups se guardan en `backups/negociosano_YYYYMMDD_HHMMSS.sql.gz`.

---

## 8. Rollback rápido

```bash
ssh deploy@IP_DEL_VPS
cd /home/deploy/negociosano

# Volver a un commit/tag anterior
git checkout v1.1.0
docker compose -f docker-compose.prod.yml build app
docker compose -f docker-compose.prod.yml up -d app

# Si hay que revertir una migración de BD
docker compose -f docker-compose.prod.yml exec app alembic downgrade -1
```

---

## 9. Comandos de operación diaria

```bash
# Ver estado de contenedores
make status

# Ver logs de la app en tiempo real
make logs

# Reiniciar solo la app (sin tocar la BD)
make restart-app

# Backup manual
make backup-db

# Deploy manual de emergencia (si CI/CD falla)
make deploy
```

---

## 10. Variables de entorno en producción

El `.env` en el VPS debe tener todos los valores reales del `.env.example`.
**Nunca** subir el `.env` al repositorio — está en `.gitignore`.

Variables críticas para producción:
- `WEBHOOK_URL` → `https://api.negociosano.com`
- `DATABASE_URL` → `postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/negociosano`
- `DB_PASSWORD` → contraseña fuerte (≥20 chars), igual que en `docker-compose.prod.yml`
- `TELEGRAM_BOT_TOKEN` → token real del bot
- `STRIPE_SECRET_KEY` → clave `sk_live_...` (¡no sk_test!)
