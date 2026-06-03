---
name: presetup
description: Ejecutar ANTES que cualquier otro agente. Cubre toda la configuración externa que el código asume que ya existe — GitHub, VPS, Cloudflare DNS, Stripe, Google Cloud, Telegram, Anthropic. Sin este agente completado, ningún otro puede funcionar correctamente.
---

# Agente 00 — Pre-setup de servicios externos

## Objetivo
Configurar todos los servicios externos y obtener todas las credenciales reales antes de escribir una sola línea de código. Al terminar este agente el fichero `.env` del VPS estará completo y el servidor estará listo para recibir deploys automáticos desde GitHub Actions.

## Arquitectura de producción

```
Internet → Cloudflare DNS → VPS (Ubuntu 24.04)
                                ├── Caddy (puerto 80/443, TLS automático)
                                ├── Docker: negociosano_app (FastAPI + Bot)
                                └── Docker: negociosano_db (PostgreSQL)

GitHub → GitHub Actions (CI tests + SSH deploy) → VPS
```

---

## Checklist de servicios

### 1. GitHub — Repositorio privado

```bash
# Crear repo privado en GitHub (interfaz web):
# github.com → New repository → negociosano → Private → sin README

# Configurar SSH key local si no está hecha
ssh-keygen -t ed25519 -C "tu@email.com" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
# Añadir en GitHub → Settings → SSH and GPG keys → New SSH key

# Clonar y configurar ramas
git clone git@github.com:TU_USUARIO/negociosano.git
cd negociosano
git checkout -b develop
git push -u origin develop
# GitHub → Settings → Branches → Default branch → cambiar a 'develop'
```

---

### 2. VPS — Provisioning en Hetzner Cloud

**Crear el servidor:**
```
console.hetzner.cloud → Nuevo proyecto: "negociosano" → Add Server

Configuración recomendada para el MVP:
  Location:    Nuremberg o Falkenstein (EU, mejor para GDPR con clientes españoles)
  Image:       Ubuntu 24.04 LTS
  Type:        CX22 (2 vCPU, 4 GB RAM, 40 GB SSD) → ~4,35€/mes
  Networking:  IPv4 pública incluida, habilitar también IPv6
  SSH keys:    Añadir tu clave pública ANTES de crear el servidor (más cómodo)
  Name:        negociosano-prod
```

> **Backups automáticos de Hetzner:** actívalos en el panel (20% sobre el precio del servidor = ~0,87€/mes adicionales). Hetzner hace snapshot diario y guarda los últimos 7. Vale la pena para un servidor de producción.

**Primera conexión y setup inicial:**
```bash
# Hetzner te muestra la IP en el panel en segundos
ssh root@IP_DEL_VPS

# Actualizar sistema
apt update && apt upgrade -y

# Instalar dependencias
apt install -y docker.io docker-compose-plugin git curl ufw fail2ban

# Firewall UFW — Hetzner también tiene Firewall Cloud en el panel
# (ambos son compatibles; UFW es suficiente para el MVP)
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP (Caddy redirige a HTTPS)
ufw allow 443/tcp    # HTTPS
ufw enable

# Crear usuario de deploy sin privilegios root
useradd -m -s /bin/bash deploy
usermod -aG docker deploy

# Estructura del proyecto
mkdir -p /home/deploy/negociosano/{logs,backups}
chown -R deploy:deploy /home/deploy/negociosano
```

> **Hetzner Cloud Firewall (opcional):** en el panel puedes configurar un firewall adicional a nivel de red antes de que el tráfico llegue al servidor. Para el MVP el UFW es suficiente, pero si quieres una capa extra: console.hetzner.cloud → Firewalls → Create Firewall → aplicar al servidor.

**SSH key para GitHub Actions** (generarla en tu máquina local, no en el VPS):
```bash
# En tu máquina local
ssh-keygen -t ed25519 -C "github-actions-negociosano" -f ~/.ssh/negociosano_deploy

# Clave PÚBLICA → añadir al VPS
ssh-copy-id -i ~/.ssh/negociosano_deploy.pub deploy@IP_DEL_VPS

# Verificar acceso
ssh -i ~/.ssh/negociosano_deploy deploy@IP_DEL_VPS "echo OK"
# → OK

# Clave PRIVADA → añadir a GitHub Secrets (ver paso 4)
cat ~/.ssh/negociosano_deploy
```

**Instalar Caddy en el VPS:**
```bash
# Como root en el VPS
apt install -y debian-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Caddyfile — proxy inverso para la app
cat > /etc/caddy/Caddyfile << 'EOF'
api.negociosano.com {
    reverse_proxy localhost:8000
    encode gzip
    log {
        output file /var/log/caddy/access.log
        format json
    }
}
EOF

systemctl enable caddy
systemctl start caddy
```

---

### 3. Cloudflare DNS — Configurar subdominio

El dominio negociosano.com ya está en Cloudflare. Añadir el subdominio de la API:

```
Cloudflare Dashboard → negociosano.com → DNS → Add record

Tipo: A
Nombre: api
Contenido: IP_DEL_VPS
Proxy: DNS only (nube gris) ← importante para que Caddy obtenga el certificado
TTL: Auto
```

Verificar que el subdominio resuelve correctamente:
```bash
dig api.negociosano.com
# Debe devolver la IP del VPS
curl https://api.negociosano.com/health
# Una vez desplegada la app: → {"status": "ok"}
```

> Una vez que Caddy haya obtenido el certificado TLS (ocurre automáticamente en el primer deploy), puedes activar el proxy de Cloudflare (nube naranja) para añadir protección DDoS. El modo SSL/TLS en Cloudflare debe estar en "Full" o "Full (Strict)".

---

### 4. GitHub Secrets — Configurar en el repositorio

```
GitHub → repo negociosano → Settings → Secrets and variables → Actions → New repository secret

VPS_HOST          → IP del VPS (ej: 65.21.x.x)
VPS_USER          → deploy
VPS_SSH_KEY       → contenido completo de ~/.ssh/negociosano_deploy (clave privada)
VPS_PROJECT_PATH  → /home/deploy/negociosano
TELEGRAM_BOT_TOKEN → token del bot (paso 5)
BOT_ADMIN_CHAT_ID  → tu Chat ID de Telegram (paso 5)
```

---

### 5. Telegram — Bot de producción

```bash
# Abrir Telegram → buscar @BotFather → /newbot
# Nombre del bot: NegocioSano
# Username: @NegocioSanoBot (debe terminar en 'bot')
# Guardar el token

# Obtener tu Chat ID:
# Buscar @userinfobot en Telegram → /start → anota tu ID numérico

# Verificar token
curl "https://api.telegram.org/bot<TOKEN>/getMe"
# → JSON con nombre y username del bot
```

**Variables obtenidas:**
```
TELEGRAM_BOT_TOKEN=<token del BotFather>
BOT_ADMIN_CHAT_ID=<tu ID numérico de Telegram>
```

---

### 6. Google Cloud — Places API

```bash
# console.cloud.google.com → Nuevo proyecto: "NegocioSano"
# APIs y servicios → Biblioteca → "Places API (New)" → Activar
# Credenciales → Crear credenciales → Clave de API
# Restricciones de la clave:
#   - Restricciones de aplicación: Direcciones IP → añadir IP del VPS
#   - Restricciones de API: Places API (New)

# Verificar
curl "https://places.googleapis.com/v1/places/ChIJN1t_tDeuEmsRUsoyG83frY4?fields=displayName,rating&key=<TU_KEY>"
# → JSON con nombre y rating del lugar
```

**Límites del tier gratuito:** $200/mes ≈ 5.000 llamadas con campo reviews.
Para 28 clientes con polling cada 2h = ~10.000 llamadas/mes → activar facturación, el crédito lo cubre.

**Variable obtenida:**
```
GOOGLE_PLACES_API_KEY=<api key>
```

---

### 7. Stripe — Productos, precios y webhook

```bash
# stripe.com → activar modo test

# Catálogo de productos → Añadir producto:
# Producto 1: "NegocioSano Pro" → 29,00€/mes recurrente → copiar Price ID
# Producto 2: "NegocioSano Multi" → 59,00€/mes recurrente → copiar Price ID

# Webhook de producción:
# Desarrolladores → Webhooks → Añadir endpoint
# URL: https://api.negociosano.com/webhook/stripe
# Eventos:
#   checkout.session.completed
#   customer.subscription.deleted
#   customer.subscription.updated
#   invoice.payment_failed
# Copiar Signing secret (whsec_...)

# Stripe CLI para desarrollo local (en tu máquina)
brew install stripe/stripe-cli/stripe    # macOS
# Linux: https://stripe.com/docs/stripe-cli#install
stripe login
stripe listen --forward-to localhost:8000/webhook/stripe
# Genera webhook secret temporal para desarrollo local
```

**Variables obtenidas:**
```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_MULTI_PRICE_ID=price_...
```

---

### 8. Anthropic — API key

```bash
# console.anthropic.com → API Keys → Create Key → "negociosano-production"

# Verificar
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: <TU_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5","max_tokens":10,"messages":[{"role":"user","content":"hola"}]}'
# → JSON con respuesta
```

**Variable obtenida:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

### 9. Email SMTP

```bash
# Opción A — Gmail (recomendada para empezar):
# Google Account → Seguridad → Contraseñas de aplicación → Correo → 16 caracteres

# Opción B — Brevo: brevo.com → 300 emails/día gratis
```

---

## .env completo en el VPS

Crear en `/home/deploy/negociosano/.env` como usuario deploy:

```bash
ssh deploy@IP_DEL_VPS
nano /home/deploy/negociosano/.env
chmod 600 /home/deploy/negociosano/.env
```

Contenido:
```bash
# Telegram
TELEGRAM_BOT_TOKEN=
BOT_ADMIN_CHAT_ID=

# Base de datos
DATABASE_URL=postgresql+asyncpg://postgres:CAMBIA_ESTO@db:5432/negociosano
DB_PASSWORD=CAMBIA_ESTO_POR_PASSWORD_SEGURA

# Google Places
GOOGLE_PLACES_API_KEY=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_MULTI_PRICE_ID=

# Anthropic
ANTHROPIC_API_KEY=

# App
WEBHOOK_URL=https://api.negociosano.com
POLLING_INTERVAL_HOURS=2
DAILY_DIGEST_HOUR=21

# Email SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=NegocioSano <tu@gmail.com>
```

---

## Verificación final — todo debe pasar antes de ejecutar el agente 01

```bash
# Desde el VPS como usuario deploy

# 1. Telegram
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | python3 -c "import sys,json; print(json.load(sys.stdin)['ok'])"
# → True

# 2. Google Places
curl -s "https://places.googleapis.com/v1/places/ChIJN1t_tDeuEmsRUsoyG83frY4?fields=displayName&key=${GOOGLE_PLACES_API_KEY}" | python3 -c "import sys,json; print(json.load(sys.stdin)['displayName'])"
# → {"text": "Sydney Opera House", ...}

# 3. Stripe
curl -s https://api.stripe.com/v1/prices/${STRIPE_PRO_PRICE_ID} \
  -u "${STRIPE_SECRET_KEY}:" | python3 -c "import sys,json; print(json.load(sys.stdin)['unit_amount'])"
# → 2900

# 4. Anthropic
curl -s https://api.anthropic.com/v1/models \
  -H "x-api-key: ${ANTHROPIC_API_KEY}" \
  -H "anthropic-version: 2023-06-01" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['id'])"
# → claude-...

# 5. Acceso SSH desde GitHub Actions (verificar manualmente)
ssh -i ~/.ssh/negociosano_deploy deploy@${VPS_HOST} "echo OK"
# → OK

# 6. Caddy corriendo
ssh deploy@IP_DEL_VPS "systemctl is-active caddy"
# → active
```

## Stripe en producción

Cuando haya primeros clientes de pago:
1. Completar KYC en Stripe
2. Cambiar `sk_test_` → `sk_live_` en el .env del VPS
3. Actualizar el webhook en Stripe Dashboard con las keys live
