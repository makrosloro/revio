# Arquitectura de Revio

Referencia técnica de cómo está construido el sistema, por qué se tomaron las decisiones principales y cómo fluyen los datos de punta a punta.

---

## Visión general

```
Cliente Telegram                 Plataformas de reseñas
     │                           Google Maps · TripAdvisor · Booking
     │ /activar /config          │
     ▼                           │ polling cada 2h
┌─────────────────┐              │
│  Bot de Telegram │◄────────────┤
│  (python-tg-bot) │             │
└────────┬────────┘         ┌────▼──────────┐
         │                  │   Scheduler   │
         ▼                  │ (APScheduler) │
┌─────────────────┐         └────┬──────────┘
│   FastAPI app   │◄─────────────┘
│                 │
│  ┌───────────┐  │    ┌─────────────────┐
│  │Middleware │  │    │   PostgreSQL     │
│  │auth/plan  │  │◄──►│                 │
│  └───────────┘  │    │ users           │
│                 │    │ businesses      │
│  ┌───────────┐  │    │ reviews         │
│  │Repositories│ │    │ alerts_log      │
│  └───────────┘  │    └─────────────────┘
└────────┬────────┘
         │
         ├──► Stripe API (pagos)
         ├──► Google Places API (reseñas)
         ├──► Anthropic API (borradores IA)
         └──► SMTP (emails de activación)
```

---

## Capas de la aplicación

### 1. Bot (app/bot/)
Punto de entrada de las interacciones del usuario. Los handlers reciben updates de Telegram y delegan inmediatamente en servicios — nunca hacen queries directas a BD ni lógica de negocio.

**Regla:** handler → servicio → repositorio. Nunca saltarse capas.

### 2. Middleware (app/bot/middleware.py)
Intercepta cada comando antes de ejecutarse. Verifica en este orden:
1. ¿El `telegram_user_id` está registrado en BD?
2. ¿La suscripción está activa (`active` o `trialing`)?
3. ¿El plan del usuario es suficiente para este comando?

Si falla cualquiera de los tres: respuesta al usuario, ejecución del handler cancelada.

### 3. Servicios (app/services/)
Contienen la lógica de negocio. Coordinan múltiples repositorios y llamadas a integraciones externas. Son la única capa que puede mezclar datos de distintas fuentes.

### 4. Repositorios (app/repositories/)
La única capa que habla con PostgreSQL. Toda query que devuelva `Business`, `Review` o `AlertLog` **siempre** filtra por `user_id`. Esta regla es el mecanismo principal de aislamiento multi-tenant.

### 5. Integraciones (app/integrations/)
Clientes para servicios externos. Cada uno encapsula su propia lógica de reintentos, manejo de errores y rate limiting. Si una integración falla, devuelve `None` o lista vacía — nunca propaga la excepción hacia arriba.

### 6. Scheduler (app/scheduler/)
Corre en el mismo proceso que FastAPI gracias al lifespan async. Dos jobs:
- `poll_reviews` — cada 2h, llama a `review_service.poll_all_businesses()`
- `heartbeat` — cada 1h, registra que el scheduler sigue vivo

### 7. Webhooks (app/webhooks/)
Endpoints HTTP que reciben eventos externos. Stripe llama a `/webhook/stripe` cuando hay eventos de pago. Telegram llama a `/{BOT_TOKEN}/webhook` con cada update del usuario.

---

## Flujo de datos: nuevo cliente

```
1. Usuario hace clic en link de pago (generado por /suscribir)
2. Stripe Checkout Session se completa
3. Stripe llama POST /webhook/stripe con evento checkout.session.completed
4. FastAPI verifica firma del webhook (STRIPE_WEBHOOK_SECRET)
5. Se crea User en BD con email, stripe_ids y token UUID (expira 48h)
6. Se envía email SMTP con token de activación
7. Usuario abre Telegram y ejecuta /activar <TOKEN>
8. Bot verifica token: válido, no expirado, no usado
9. Se vincula telegram_user_id al User en BD, token se borra
10. Usuario ya puede usar /config, /agregar, etc.
```

## Flujo de datos: alerta de reseña negativa

```
1. APScheduler dispara poll_reviews cada 2h
2. review_service obtiene todos los Business activos con su User (JOIN)
3. Para cada negocio: GooglePlacesClient.get_reviews(place_id)
4. Para cada reseña: review_repo.exists(platform, review_id)
5. Si no existe: clasificar → rating ≤ 3 = negative, rating ≥ 4 = positive
6. review_repo.create(..., review_type=tipo)
7. Si negative:
   a. (Fase 2) AnthropicClient.generate_negative_draft(review, business)
   b. bot.send_message con alerta + borrador + botones inline [✅ Publicar] [✏️ Editar] [❌ Descartar]
   c. alert_log.create(review_id, draft_text, sent_at)
```

## Flujo de datos: resumen diario de positivas

```
1. APScheduler dispara send_daily_digest cada día a las 21:00
2. Para cada User activo con plan Pro o Multi:
3. Para cada Business activo: review_repo.get_undigested_positives(business_id, today)
4. Si hay positivas nuevas:
   a. (Fase 2) AnthropicClient.generate_positive_draft() para cada una (máx 5)
   b. bot.send_message con resumen + borradores + botones de publicación
   c. review_repo.mark_digest_sent(ids)
5. Si no hay positivas: no enviar nada
```

## Flujo de datos: publicación directa en Google (Fase 3, plan Multi)

```
1. Usuario pulsa [✅ Publicar en Google] en el mensaje de Telegram
2. Callback handler recibe el evento inline
3. publish_service verifica que business tiene GBP vinculado
4. Si access_token expirado: GBPClient.refresh_access_token()
5. GBPClient.reply_to_review(location_name, review_id, draft_text)
6. Google Maps muestra la respuesta en < 10 segundos
7. alerts_log actualiza: published_at, published_text, publish_status = published
8. Bot confirma: "✅ Respuesta publicada en Google Maps"
```

---

## Decisiones de diseño y por qué

### ¿Por qué APScheduler y no Celery?
Celery requiere Redis y un proceso worker separado. Para el MVP en NAS con 5-30 clientes, APScheduler corre en el mismo proceso de FastAPI sin infraestructura adicional. La migración a Celery está documentada en el agente 04 para cuando escale.

### ¿Por qué alertas inmediatas para negativas y resumen diario para positivas?
Un restaurante popular puede recibir 10 reseñas positivas en un sábado. Mandar 10 alertas inmediatas es spam y destruye la experiencia del producto. Las negativas sí son urgentes — cada hora sin respuesta aumenta el daño. Las positivas no son urgentes — el resumen de las 21:00 agrupa el día sin interrumpir el servicio.

### ¿Por qué la publicación directa en Google es solo plan Multi?
Es el diferenciador más potente del producto y el argumento de venta más claro para justificar el precio de 59€. Antes era difícil explicar por qué Multi cuesta el doble que Pro. Ahora la diferencia es concreta y medible: con Multi no abres el navegador, publicas desde Telegram.

### ¿Por qué prompts distintos para negativas y positivas?
Una respuesta positiva bien hecha menciona algo específico de lo que el cliente dijo e invita a volver — nunca es genérica. Una respuesta negativa debe desactivar la queja sin admitir negligencia. Son objetivos completamente distintos que requieren prompts distintos, no el mismo con tono cambiado.

### ¿Por qué Telegram y no una app?
Open rate del 90% frente al 22% del email. El propietario de un bar ya tiene Telegram en el móvil. Sin app que instalar, sin notificaciones push que configurar, sin coste de desarrollo de app nativa.

### ¿Por qué token de activación por email y no registro web?
Elimina la necesidad de una landing page con formulario de registro en el MVP. El flujo completo ocurre dentro de Telegram y el email de Stripe. Menos fricción, menos código, mismo resultado.

### ¿Por qué SQLite en tests y no PostgreSQL?
Los tests son más rápidos (no hay proceso externo) y el CI no necesita configurar un servicio de BD. SQLAlchemy async es compatible con ambos. Las diferencias entre SQLite y PostgreSQL no afectan a los caminos críticos que se testean.

---

## Modelo de datos

```
users
  id, telegram_user_id (UNIQUE), email (UNIQUE)
  stripe_customer_id, stripe_sub_id
  plan (free|pro|multi), sub_status (inactive|active|trialing|cancelled|past_due)
  sub_ends_at, activation_token, token_expires_at
  created_at

businesses
  id, user_id → users(id) ON DELETE CASCADE
  name, google_place_id, tripadvisor_url, booking_url
  response_tone (profesional|cercano|formal)
  gbp_location_name, gbp_access_token, gbp_refresh_token, gbp_token_expires_at
  auto_publish_positive (boolean, default false)
  active, created_at

reviews
  id, business_id → businesses(id) ON DELETE CASCADE
  platform (google|tripadvisor|booking)
  review_id (único por plataforma), rating, text, author
  review_type (negative|positive)   ← clasificación por rating
  reviewed_at, alerted_at, digest_sent_at

alerts_log
  id, business_id, review_id → reviews(id)
  sent_at, draft_text, draft_type (negative|positive), ai_draft_tokens
  published_at, published_text, publish_status (pending|published|discarded|failed)
```

**Índices críticos para rendimiento:**
- `users.telegram_user_id` — consultado en cada update del bot
- `users.stripe_sub_id` — consultado en cada webhook de Stripe
- `reviews.(platform, review_id)` — consultado en cada ciclo de polling para deduplicación
- `businesses.user_id` — consultado en cada comando del bot

---

## Límites conocidos del MVP

| Límite | Valor actual | Cuándo escalar |
|--------|-------------|----------------|
| Negocios sin coste de API | ~28 (tier free de Google) | Al superar 28 clientes Pro |
| Proceso único (sin workers) | 1 instancia FastAPI | Al superar 100 clientes |
| Scheduler en proceso | APScheduler | Al superar 50 negocios activos |
| Infraestructura | NAS Synology | Al superar 50 clientes o ingresos > 1.000€/mes |
