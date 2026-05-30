---
name: ai-drafts
description: Usar para construir o modificar la generación de borradores de respuesta con Claude API — tanto para reseñas negativas como positivas. Fase 2 — implementar cuando el polling esté estable.
---

# Agente 05 — Borradores de Respuesta con IA (Fase 2)

## Prerequisito
Agentes 01-03 completados y estables en producción. Al menos 1 semana de polling activo.

## Objetivo
Generar borradores de respuesta personalizados para reseñas negativas (en alerta inmediata) y positivas (en el resumen diario). Los prompts son completamente distintos — no es el mismo texto con tono cambiado.

---

## Dos tipos de borrador con lógica diferente

### Borradores para negativas
Objetivo: desactivar la queja, empatizar sin admitir negligencia, ofrecer solución, recuperar la confianza. El tono es importante: nunca defensivo, nunca servil.

**System prompt para negativas:**
```
Eres un experto en gestión de reputación online para negocios de hostelería y retail en España.
Tu tarea es redactar respuestas a reseñas negativas en Google Maps, TripAdvisor o Booking.
La respuesta debe:
- Empezar agradeciendo el feedback (no el tono, el feedback)
- Reconocer el problema de forma específica sin admitir negligencia legal
- Ofrecer una solución concreta o invitar a contactar directamente
- Ser breve: máximo 80 palabras
- Tono: {tone} (profesional / cercano / formal)
- Nunca usar frases genéricas como "lamentamos los inconvenientes"
Responde SOLO con el texto del borrador, sin comillas ni explicaciones.
```

**User prompt para negativas:**
```
Negocio: {business_name}
Plataforma: {platform}
Rating: {rating}/5
Reseña de {author}: "{review_text}"
```

### Borradores para positivas
Objetivo: reforzar la relación con el cliente, personalizar para que no parezca un bot, mencionar algo específico de la reseña e invitar a volver. En Google, las respuestas personalizadas a positivas tienen más impacto en el ranking que las genéricas.

**System prompt para positivas:**
```
Eres un experto en gestión de reputación online para negocios de hostelería y retail en España.
Tu tarea es redactar respuestas a reseñas positivas en Google Maps, TripAdvisor o Booking.
La respuesta debe:
- Agradecer de forma genuina y específica (mencionar algo concreto de lo que dijo)
- Ser cálida pero no exagerada ni aduladora
- Invitar a volver con naturalidad
- Ser breve: máximo 60 palabras
- Tono: {tone} (profesional / cercano / formal)
- Nunca empezar todas las respuestas igual — variar el inicio
Responde SOLO con el texto del borrador, sin comillas ni explicaciones.
```

**User prompt para positivas:**
```
Negocio: {business_name}
Plataforma: {platform}
Rating: {rating}/5
Reseña de {author}: "{review_text}"
```

---

## Tareas en orden

### 1. Cliente Anthropic (app/integrations/anthropic_client.py)
Clase `AnthropicClient` con dos métodos:

```python
async def generate_negative_draft(review: dict, business: Business) -> str
async def generate_positive_draft(review: dict, business: Business) -> str
```

Ambos usan `claude-haiku-4-5`, `max_tokens=250`, temperatura 0.7 para negativas y 0.8 para positivas (más variedad en positivas para que no parezcan robots).

Si la llamada falla: devolver string vacío, NO lanzar excepción. La alerta/resumen se envía igualmente sin borrador.

### 2. Integrar borradores en alertas negativas
En `review_service.poll_all_businesses()`, después de detectar una negativa y antes de enviar el mensaje:

```python
draft = ""
if user.plan in ("pro", "multi"):
    draft = await anthropic_client.generate_negative_draft(review, business)
message = format_negative_alert(review, business, draft)
await bot.send_message(user.telegram_user_id, message)
```

### 3. Integrar borradores en el resumen diario
En `review_service.send_daily_digest()`, generar un borrador para cada positiva del resumen (máximo 5 borradores por envío para controlar costes):

```python
for review in positive_reviews[:5]:
    draft = await anthropic_client.generate_positive_draft(review, business)
    review.draft_text = draft   # temporal, para el formato del mensaje
```

El resumen diario incluye cada reseña positiva con su borrador debajo, como una lista expandible.

### 4. Comando /responder (app/bot/handlers/responder.py)
Protegido (pro). Permite regenerar un borrador para cualquier reseña reciente:

```
/responder → muestra botones inline con las últimas 5 reseñas sin responder
           → usuario selecciona una
           → bot genera nuevo borrador (temperatura 0.9 para más variedad)
           → muestra el borrador con botones: [🔄 Regenerar] [✅ Guardar]
```

### 5. Tono personalizable por negocio
Añadir campo `response_tone VARCHAR DEFAULT 'cercano'` a tabla `businesses` (migración Alembic).
Valores: `profesional`, `cercano`, `formal`.
Configurable con /config → "Cambiar tono de respuestas".

### 6. Control de costes
Registrar en `alerts_log.ai_draft_tokens` el número de tokens usados.
Añadir migración con campo `draft_type VARCHAR` (negative|positive) a `alerts_log`.

Estimación de costes con scope ampliado:
- 30 clientes Pro · 2 negativas/semana · 4 semanas = 240 borradores negativos/mes
- 30 clientes Pro · 5 positivas/día · 30 días (máx 5 borradores/día) = 4.500 borradores positivos/mes
- Total tokens estimados: ~2.400.000 tokens/mes
- Coste Claude Haiku: ~0,25€/1M tokens → ~0,60€/mes total — sigue siendo despreciable

### 7. Formato actualizado del resumen diario con borradores

```
🌟 Resumen de hoy — {business.name}

{N} reseña(s) positiva(s) recibidas:

⭐⭐⭐⭐⭐ {author_1}
"{texto[:100]}..."
💬 Borrador: "{draft_1}"

⭐⭐⭐⭐ {author_2}
"{texto[:100]}..."
💬 Borrador: "{draft_2}"

Usa /responder para regenerar cualquier borrador.
```

---

## Verificación

```bash
# Test borrador negativo
python -c "
import asyncio
from app.integrations.anthropic_client import AnthropicClient
client = AnthropicClient()
draft = asyncio.run(client.generate_negative_draft(
    review={'rating': 2, 'text': 'Llevamos esperando 45 minutos y la comida llegó fría', 'author': 'María G.', 'platform': 'google'},
    business=type('B', (), {'name': 'Bar El Rincón', 'response_tone': 'cercano'})()
))
print('NEGATIVO:', draft)
print('Palabras:', len(draft.split()))
"

# Test borrador positivo
python -c "
import asyncio
from app.integrations.anthropic_client import AnthropicClient
client = AnthropicClient()
draft = asyncio.run(client.generate_positive_draft(
    review={'rating': 5, 'text': 'El pulpo a la gallega estaba increíble y el trato fue excelente', 'author': 'Carlos M.', 'platform': 'google'},
    business=type('B', (), {'name': 'Bar El Rincón', 'response_tone': 'cercano'})()
))
print('POSITIVO:', draft)
print('Palabras:', len(draft.split()))
# Debe ser más corto que el negativo y mencionar el pulpo o el trato
"
```
