---
name: presetup
description: Ejecutar ANTES que cualquier otro agente. Cubre toda la configuración externa que el código asume que ya existe — GitHub, Stripe, Google Cloud, Telegram, Cloudflare, Anthropic. Sin este agente completado, ningún otro puede funcionar correctamente.
---

# Agente 00 — Pre-setup de servicios externos

## Objetivo
Configurar todos los servicios externos y obtener todas las credenciales reales antes de escribir una sola línea de código. Al terminar este agente, el fichero `.env` del NAS estará completo.

## Checklist de servicios

### 1. GitHub — Repositorio privado

```bash
# Crear repo privado en GitHub (interfaz web):
# github.com → New repository → Private → sin README (lo crearemos nosotros)
# Nombre sugerido: revio

# Configurar SSH key si no está hecha
ssh-keygen -t ed25519 -C "tu@email.com" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
# Añadir en GitHub → Settings → SSH and GPG keys → New SSH key

# Clonar y configurar repo inicial
git clone git@github.com:TU_USUARIO/revio.git
cd revio
git checkout -b develop
git push -u origin develop

# En GitHub → Settings → Branches → Default branch → cambiar a 'develop'
```

### 2. Telegram — Bot de producción

```bash
# 1. Abrir Telegram → buscar @BotFather → /newbot
# 2. Nombre del bot: Revio (o el que elijas)
# 3. Username: @tu_reviobot (debe terminar en 'bot')
# 4. Guardar el token → TELEGRAM_BOT_TOKEN

# Obtener tu propio Chat ID (para BOT_ADMIN_CHAT_ID):
# Buscar @userinfobot en Telegram → /start → te muestra tu ID numérico

# Verificar que el token funciona
curl "https://api.telegram.org/bot<TOKEN>/getMe"
# Debe devolver JSON con el nombre y username del bot
```

**Variables obtenidas:**
```
TELEGRAM_BOT_TOKEN=<token del BotFather>
BOT_ADMIN_CHAT_ID=<tu ID numérico de Telegram>
```

### 3. Google Cloud — Places API

```bash
# 1. Ir a console.cloud.google.com
# 2. Crear nuevo proyecto: "Revio"
# 3. Activar la API: APIs y servicios → Biblioteca → buscar "Places API (New)" → Activar
#    IMPORTANTE: activar "Places API (New)", no la legacy "Places API"
# 4. Crear credenciales: APIs y servicios → Credenciales → Crear credenciales → Clave de API
# 5. Restringir la clave:
#    - Restricciones de aplicación: Direcciones IP → añadir IP del NAS
#    - Restricciones de API: Places API (New)
# 6. Copiar la API key

# Verificar con un Place ID real (busca cualquier restaurante en Google Maps y copia el ID de la URL)
curl "https://places.googleapis.com/v1/places/ChIJN1t_tDeuEmsRUsoyG83frY4?fields=displayName,rating,reviews&key=<TU_KEY>"
# Debe devolver nombre, rating y reseñas del lugar
```

**Variable obtenida:**
```
GOOGLE_PLACES_API_KEY=<tu API key>
```

**Límites del tier gratuito:** $200/mes de crédito ≈ 5.000 llamadas con campo reviews. Para 28 negocios con polling cada 2h = 28 × 12 = 336 llamadas/día = ~10.000/mes → necesitarás activar facturación pero el crédito cubre los primeros meses.

### 4. Stripe — Productos y precios

```bash
# 1. Crear cuenta en stripe.com (modo test primero)
# 2. Activar el modo test (toggle en el dashboard)

# En Stripe Dashboard → Catálogo de productos → Añadir producto:

# PRODUCTO 1: Revio Pro
# Nombre: Revio Pro
# Precio: 29,00 € / mes / recurrente
# Guardar → copiar el Price ID (empieza por price_)

# PRODUCTO 2: Revio Multi  
# Nombre: Revio Multi
# Precio: 59,00 € / mes / recurrente
# Guardar → copiar el Price ID

# Configurar webhook (modo test):
# Stripe Dashboard → Desarrolladores → Webhooks → Añadir endpoint
# URL: https://TU_TUNNEL.trycloudflare.com/webhook/stripe (provisional para test)
# Eventos a escuchar:
#   - checkout.session.completed
#   - customer.subscription.deleted
#   - customer.subscription.updated
#   - invoice.payment_failed
# Guardar → copiar el Signing secret (empieza por whsec_)

# Instalar Stripe CLI para desarrollo local
brew install stripe/stripe-cli/stripe         # macOS
# Para Linux: ver https://stripe.com/docs/stripe-cli#install
stripe login
stripe listen --forward-to localhost:8000/webhook/stripe
# Esto genera un webhook secret temporal para desarrollo — usarlo en .env local
```

**Variables obtenidas:**
```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_MULTI_PRICE_ID=price_...
```

### 5. Anthropic — API key

```bash
# console.anthropic.com → API Keys → Create Key
# Nombre: "revio-production"
# Guardar inmediatamente — no se vuelve a mostrar

# Verificar
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: <TU_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5","max_tokens":10,"messages":[{"role":"user","content":"hola"}]}'
# Debe devolver JSON con una respuesta
```

**Variable obtenida:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

### 6. Cloudflare Tunnel — NAS

```bash
# cloudflare.com → Zero Trust → Access → Tunnels → Create tunnel
# Nombre: "revio-nas"
# Instalar connector: seleccionar Docker
# Copiar el token del tunnel

# Configurar el public hostname en el tunnel:
# Subdomain: api (o el que elijas)
# Domain: tu dominio (necesitas tener un dominio apuntando a Cloudflare)
# Service: http://app:8000

# La URL pública resultante: https://api.tudominio.com
```

**Variables obtenidas:**
```
CLOUDFLARE_TUNNEL_TOKEN=<token del tunnel>
WEBHOOK_URL=https://api.tudominio.com
```

### 7. Email SMTP para activaciones

```bash
# Opción A (recomendada para empezar): Gmail con contraseña de aplicación
# Google Account → Seguridad → Verificación en dos pasos → Contraseñas de aplicación
# Crear contraseña para "Correo" → guardar los 16 caracteres

# Opción B: Brevo (antes Sendinblue) — 300 emails/día gratis
# brevo.com → Settings → SMTP & API → SMTP

# Variables para ambas opciones:
SMTP_HOST=smtp.gmail.com          # o smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USER=tu@gmail.com
SMTP_PASSWORD=<contraseña de aplicación de 16 chars>
SMTP_FROM=Revio <tu@gmail.com>
```

---

## .env completo para el NAS

Al terminar este agente, crear el fichero en `/volume1/docker/revio/.env`:

```bash
# Bot de Telegram
TELEGRAM_BOT_TOKEN=
BOT_ADMIN_CHAT_ID=

# Base de datos (interna Docker — no cambiar)
DATABASE_URL=postgresql+asyncpg://postgres:CAMBIA_ESTO@db:5432/revio
DB_PASSWORD=CAMBIA_ESTO_POR_CONTRASEÑA_SEGURA

# Google Places API
GOOGLE_PLACES_API_KEY=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_MULTI_PRICE_ID=

# Anthropic
ANTHROPIC_API_KEY=

# Cloudflare y URL pública
CLOUDFLARE_TUNNEL_TOKEN=
WEBHOOK_URL=https://api.tudominio.com

# Email SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=Revio <tu@gmail.com>

# Config del scheduler
POLLING_INTERVAL_HOURS=2
```

---

## Verificación final

```bash
# Todos estos comandos deben dar respuesta sin error antes de pasar al agente 01

# Telegram
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | jq .ok
# → true

# Google Places
curl "https://places.googleapis.com/v1/places/ChIJN1t_tDeuEmsRUsoyG83frY4?fields=displayName&key=${GOOGLE_PLACES_API_KEY}"
# → JSON con nombre del lugar

# Stripe
curl https://api.stripe.com/v1/prices/${STRIPE_PRO_PRICE_ID} \
  -u "${STRIPE_SECRET_KEY}:" | jq .unit_amount
# → 2900

# Anthropic
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: ${ANTHROPIC_API_KEY}" \
  -H "anthropic-version: 2023-06-01" | jq '.models[0].id'
# → "claude-..."
```

## Estado de Stripe en producción

Cuando se acerque el lanzamiento real (primeros clientes de pago):
1. Completar el proceso KYC en Stripe (verificación de identidad y negocio)
2. Cambiar las keys de `sk_test_` a `sk_live_`
3. Recrear el webhook con la URL de producción y las keys live
4. Actualizar el `.env` del NAS con las keys live
