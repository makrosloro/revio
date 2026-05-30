---
name: scraping
description: Usar para construir o modificar el scraping de TripAdvisor y Booking.com. Es fase 2 — no implementar hasta tener clientes de pago en el plan Pro.
---

# Agente 04 — Scraping TripAdvisor y Booking (Fase 2)

## Prerequisito
Agentes 01-03 completados y funcionando. Al menos 5 clientes Pro pagando. El agente 03 (Google) es estable y no tiene bugs activos.

## Objetivo
Añadir TripAdvisor y Booking.com como fuentes de reseñas. El sistema de alertas ya existe — este agente solo añade nuevas fuentes que alimentan el mismo pipeline.

## Principios de scraping responsable
- Máximo 2 requests por dominio cada 6 horas por negocio (no 2h como Google)
- Delays aleatorios entre 3 y 8 segundos entre requests
- User-Agent rotation desde lista de browsers reales actualizados
- Si el sitio devuelve 429 o 503: backoff de 24h para ese negocio concreto, log de warning, NO alerta al admin salvo que sea el 3er fallo consecutivo
- Nunca paralelizar requests al mismo dominio

## Tareas en orden

### 1. Playwright setup
Añadir `playwright` a requirements.txt. En Dockerfile: `RUN playwright install chromium --with-deps`. Crear `app/integrations/browser.py` con context manager async que devuelve un `Page` configurado (viewport, user-agent, headers comunes, timeout 30s).

### 2. TripAdvisor scraper (app/integrations/tripadvisor.py)
Clase `TripAdvisorClient` con método `get_reviews(url) → List[dict]`.

Estrategia: navegar a la URL de la ficha, esperar a que carguen las reseñas (selector CSS de la sección de reseñas), extraer las 10 más recientes. Campos a extraer: `review_id` (del DOM o URL), `rating` (número de burbujas), `text`, `author`, `date`.

Manejar: página de verificación de bot → devolver lista vacía + log. Cambio de estructura del DOM → capturar excepción, log de error con screenshot para debug.

El `review_id` para TripAdvisor será el hash MD5 de `(author + date + primeros 50 chars de texto)` si no hay ID en el DOM.

### 3. Booking scraper (app/integrations/booking.py)
Clase `BookingClient` con método `get_reviews(property_url) → List[dict]`.

Booking tiene anti-bot más agresivo. Estrategia alternativa preferida: muchas propiedades tienen RSS de reseñas o endpoints JSON públicos accesibles directamente. Investigar primero si `{property_url}/reviews.json` existe antes de usar Playwright. Si no, usar Playwright con delays largos (5-10s).

### 4. Ampliar modelo Business
Añadir migración Alembic con campos: `tripadvisor_url VARCHAR`, `booking_url VARCHAR`. Ambos opcionales.

### 5. Ampliar /agregar en el bot
Después de guardar Google Place ID, preguntar: "¿Tienes ficha en TripAdvisor? (Pega el link o escribe /saltar)". Mismo patrón para Booking. Guardar las URLs.

### 6. Ampliar poll_all_businesses()
Después del polling de Google, iterar los negocios con `tripadvisor_url` no nulo y llamar a `TripAdvisorClient`. Mismo patrón para Booking. Misma lógica de deduplicación por `(platform, review_id)`.

### 7. Scheduler ajustado
Separar jobs: Google cada 2h (como ahora), TripAdvisor + Booking cada 6h. Así se reduce el riesgo de bloqueos.

## Verificación
```bash
# Test TripAdvisor con URL real
python -c "
import asyncio
from app.integrations.tripadvisor import TripAdvisorClient
client = TripAdvisorClient()
reviews = asyncio.run(client.get_reviews('https://www.tripadvisor.es/Restaurant_Review-...'))
print(f'{len(reviews)} reseñas')
"

# Verificar que los datos van a la misma tabla reviews con platform='tripadvisor'
psql $DATABASE_URL -c "SELECT platform, COUNT(*) FROM reviews GROUP BY platform;"
```
