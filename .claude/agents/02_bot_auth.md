---
name: bot-auth
description: Usar para construir o modificar el sistema de autenticación del bot de Telegram, el flujo de activación, los webhooks de Stripe y el middleware de suscripción.
---

# Agente 02 — Bot, Auth y Stripe

## Prerequisito
Agente 01 completado. Las tablas `users` y `businesses` existen en la BD.

## Objetivo
Sistema completo de autenticación: un usuario paga en Stripe → recibe token por email → activa su cuenta en el bot → el middleware bloquea todo acceso no autorizado.

## Tareas en orden

### 1. Repositorio de usuarios (app/repositories/user_repo.py)
Métodos async:
- `get_by_telegram_id(telegram_user_id)` → User | None
- `get_by_email(email)` → User | None
- `get_by_activation_token(token)` → User | None
- `create_from_stripe(email, stripe_customer_id, stripe_sub_id, plan)` → User (genera token UUID, expira en 48h)
- `activate(user_id, telegram_user_id)` → User (vincula telegram_user_id, borra token)
- `update_subscription_status(stripe_sub_id, status)` → None

### 2. Middleware de autorización (app/bot/middleware.py)
Decorador `require_subscription(min_plan="pro")`. Lógica:
1. Obtener `telegram_user_id` del update
2. Buscar user en BD
3. Si no existe → mensaje "Activa tu cuenta con /activar TOKEN"
4. Si `sub_status` no es `active` ni `trialing` → mensaje con link a /suscribir
5. Si plan insuficiente → mensaje indicando qué plan necesita
6. Si todo OK → inyectar `user` en kwargs y ejecutar el handler

Planes en orden: `free < pro < multi`. Comparar con índice de lista.

### 3. Handlers del bot (app/bot/handlers/)

**start.py** — `/start`
Sin protección. Mensaje de bienvenida con descripción del servicio en 3 líneas y lista de comandos disponibles.

**activar.py** — `/activar <TOKEN>`
Sin protección. Validar token, comprobar expiración, comprobar que no está vinculado a otro Telegram, vincular, confirmar al usuario. Ver lógica completa en el plan técnico principal.

**suscribir.py** — `/suscribir`
Sin protección. Crear Stripe Checkout Session con el `telegram_user_id` en los metadatos. Enviar link de pago como botón inline. Dos botones: Pro (29€/mes) y Multi (59€/mes).

**config.py** — `/config`
Protegido (pro). Mostrar negocios activos del usuario como lista numerada. Si no tiene ninguno, invitar a usar /agregar.

**agregar.py** — `/agregar`
Protegido (pro). Flujo conversacional con ConversationHandler:
- Estado 1: pedir nombre del negocio
- Estado 2: pedir link de Google Maps
- Estado 3: extraer Place ID del link, confirmar, guardar en BD
- /cancelar en cualquier punto sale del flujo

**pausa.py** — `/pausa` y `/reanudar`
Protegido (pro). Si tiene varios negocios, mostrar botones inline para seleccionar cuál pausar/reanudar.

**estado.py** — `/estado`
Protegido (free). Mostrar plan actual, fecha de próxima renovación (desde Stripe), número de negocios monitorizados.

### 4. Webhook de Stripe (app/webhooks/stripe.py)
Endpoint `POST /webhook/stripe`. Verificar firma con `stripe.Webhook.construct_event`.

Eventos a manejar:
- `checkout.session.completed` → crear user + token + enviar email de activación
- `customer.subscription.deleted` → marcar `sub_status = cancelled`
- `customer.subscription.updated` → actualizar plan y status (para upgrades/downgrades)
- `invoice.payment_failed` → marcar `sub_status = past_due`, avisar al usuario por Telegram si tiene `telegram_user_id`

### 5. Servicio de email (app/services/email_service.py)
Enviar email de activación. Usar SMTP estándar (smtplib, configurado en `.env`). Plantilla del email en texto plano + HTML mínimo. El email incluye: el token, instrucción de copiar y pegar en el bot, y enlace directo `https://t.me/BOTNAME?start=TOKEN` que auto-ejecuta /activar.

### 6. Registro de handlers en main.py
Añadir todos los handlers al `Application`. Configurar webhook de Telegram en el lifespan (set_webhook con la URL pública).

## Verificación
```bash
# Simular webhook de Stripe con Stripe CLI
stripe listen --forward-to localhost:8000/webhook/stripe
stripe trigger checkout.session.completed

# Verificar que se creó el user en BD
psql $DATABASE_URL -c "SELECT email, sub_status, activation_token FROM users;"

# Probar el bot manualmente
# 1. Enviar /start → debe responder sin error
# 2. Enviar /config → debe responder "Activa tu cuenta..."
# 3. Enviar /activar TOKEN_GENERADO → debe vincular y confirmar
# 4. Enviar /config → ahora debe responder normalmente
```
