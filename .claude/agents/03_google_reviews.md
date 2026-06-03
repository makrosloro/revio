---
name: google-reviews
description: Usar para construir o modificar el sistema de polling de reseñas de Google Maps, la clasificación por sentimiento, el envío de alertas inmediatas para negativas y el resumen diario de positivas.
---

# Agente 03 — Google Reviews, Alertas y Resumen Diario

## Prerequisito
Agentes 01 y 02 completados. El bot responde comandos y el sistema de auth funciona.

## Objetivo
Polling de Google Maps cada 2 horas. Las reseñas negativas (≤3★) generan alerta inmediata con borrador. Las positivas (≥4★) se acumulan y se envían como resumen diario a las 21:00. Así el propietario no recibe spam en días con muchas reseñas buenas.

---

## Clasificación de reseñas

```python
def classify_review(rating: int) -> str:
    if rating <= 3:
        return "negative"   # alerta inmediata
    elif rating == 4:
        return "positive"   # resumen diario
    else:                   # 5 estrellas
        return "positive"   # resumen diario
```

La lógica de notificación es completamente distinta según el tipo:
- **negative** → alerta inmediata, prioritaria, con borrador de respuesta (fase 2)
- **positive** → se acumula en BD, se envía como resumen diario a las 21:00

---

## Tareas en orden

### 1. Actualizar modelo Review (migración Alembic)
Añadir campo `review_type VARCHAR NOT NULL DEFAULT 'negative'` con valores posibles: `negative`, `positive`. Añadir índice en `(business_id, review_type, alerted_at)` para las queries del resumen diario.

### 2. Repositorio de negocios (app/repositories/business_repo.py)
- `get_all_active()` → List[Business] con User en eager load (evitar N+1)
- `get_by_user(user_id)` → List[Business]
- `get_by_id(business_id, user_id)` → Business | None — SIEMPRE con user_id
- `create(user_id, name, google_place_id)` → Business
- `set_active(business_id, user_id, active: bool)` → None

### 3. Repositorio de reseñas (app/repositories/review_repo.py)
- `exists(platform, review_id)` → bool
- `create(business_id, platform, review_id, rating, text, author, reviewed_at, review_type)` → Review
- `get_undigested_positives(business_id, user_id, date)` → List[Review]
  Devuelve positivas de hoy que aún no han sido incluidas en el resumen (`digest_sent_at IS NULL`)
- `mark_digest_sent(review_ids: list[int])` → None — actualiza `digest_sent_at = now()`
- `get_recent_negatives(business_id, user_id, limit=10)` → List[Review]

Añadir campo `digest_sent_at TIMESTAMPTZ NULL` a la tabla reviews (migración Alembic).

### 4. Integración Google Places (app/integrations/google_places.py)
Clase `GooglePlacesClient` con método `get_reviews(place_id) → List[dict]`.
Usar la API `places.googleapis.com/v1/places/{place_id}` con field mask `reviews`.
Manejo: rate limit (429) → backoff exponencial máximo 3 intentos. Cuota agotada → alerta al admin.

### 5. Servicio de polling (app/services/review_service.py)

**poll_all_businesses()** — ejecutado cada 2h por el scheduler:
```
Para cada Business activo con User en eager load:
  → GooglePlacesClient.get_reviews(place_id)
  → Para cada review recibida:
      → review_repo.exists(platform, review_id) → si existe: skip
      → Clasificar: rating ≤ 3 → negative, rating ≥ 4 → positive
      → review_repo.create(..., review_type=tipo)
      → Si negative Y user.plan != 'free' Y sub activa:
          → bot.send_message(alerta inmediata)
          → alert_log.create(...)
      → Si negative Y user.plan == 'free':
          → bot.send_message(alerta sin borrador)
```

**send_daily_digest()** — ejecutado cada día a las 21:00:
```
Para cada User activo con plan Pro o Multi:
  Para cada Business activo del user:
    → review_repo.get_undigested_positives(business_id, user_id, today)
    → Si hay reseñas positivas nuevas:
        → Construir mensaje resumen
        → bot.send_message(resumen)
        → review_repo.mark_digest_sent(ids de esas reseñas)
    → Si no hay positivas nuevas: no enviar nada (no molestar)
```

### 6. Formatos de mensaje

**Alerta inmediata negativa (plan Free):**
```
🔴 Nueva reseña negativa — {business.name}

⭐ {rating}/5 · {author} · {fecha}
📍 Google Maps

"{texto_reseña}"

💡 Responder rápido mejora tu posicionamiento en Google.
Contrata el plan Pro para recibir un borrador de respuesta listo para copiar.
```

**Alerta inmediata negativa (plan Pro/Multi):**
```
🔴 Nueva reseña negativa — {business.name}

⭐ {rating}/5 · {author} · {fecha}
📍 Google Maps

"{texto_reseña}"

💬 Borrador de respuesta:
"{borrador_ia}"    ← se añade en fase 2 con el agente 05

[✅ Marcar como vista]
```

**Resumen diario de positivas:**
```
🌟 Resumen de hoy — {business.name}

Has recibido {N} reseña(s) positiva(s):

⭐⭐⭐⭐⭐ {author_1} · "{texto[:80]}..."
⭐⭐⭐⭐  {author_2} · "{texto[:80]}..."
⭐⭐⭐⭐⭐ {author_3} · "{texto[:80]}..."

💡 Responder a las buenas también mejora tu ranking en Google.
Usa /responder para ver borradores de respuesta.
```

Si hay más de 5 positivas en un día: mostrar las 5 con mayor rating y añadir "y {N-5} más".

### 7. Comando /resenas (app/bot/handlers/resenas.py)
Protegido (free). Subcomandos via botones inline:
- "Ver negativas recientes" → últimas 5 negativas
- "Ver positivas de hoy" → positivas de hoy sin responder (solo Pro/Multi)

### 8. Scheduler — dos jobs (app/scheduler/tasks.py)

```python
scheduler.add_job(
    poll_all_businesses,
    trigger=IntervalTrigger(hours=POLLING_INTERVAL_HOURS),
    id="poll_reviews",
    replace_existing=True,
    next_run_time=datetime.now()   # ejecutar inmediatamente al arrancar
)

scheduler.add_job(
    send_daily_digest,
    trigger=CronTrigger(hour=DAILY_DIGEST_HOUR, minute=0, timezone="Europe/Madrid"),
    id="daily_digest",
    replace_existing=True,
)
```

### 9. Extraer Place ID del link de Google Maps (app/services/places_service.py)
Función `extract_place_id_from_url(url) → str | None`. Cubrir formatos:
- `maps.google.com/?cid=...`
- `google.com/maps/place/.../@lat,lng,...`
- URLs acortadas `goo.gl/maps/...` → seguir redirect con httpx

---

## Verificación

```bash
# Test del polling con un Place ID real
python -c "
import asyncio
from app.integrations.google_places import GooglePlacesClient
client = GooglePlacesClient()
reviews = asyncio.run(client.get_reviews('ChIJ...PLACE_ID...'))
negativas = [r for r in reviews if r['rating'] <= 3]
positivas = [r for r in reviews if r['rating'] >= 4]
print(f'Total: {len(reviews)} | Negativas: {len(negativas)} | Positivas: {len(positivas)}')
"

# Verificar clasificación en BD tras un ciclo de polling
psql $DATABASE_URL -c "SELECT review_type, COUNT(*) FROM reviews GROUP BY review_type;"
# → negative: N / positive: M

# Simular el resumen diario manualmente
python -c "
import asyncio
from app.services.review_service import send_daily_digest
asyncio.run(send_daily_digest())
"
```
