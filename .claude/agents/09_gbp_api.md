---
name: gbp-api
description: Usar para construir la integración con Google Business Profile API — permite publicar respuestas a reseñas directamente en Google con un botón desde Telegram. Fase 3 — implementar solo cuando haya 20+ clientes Multi activos.
---

# Agente 09 — Google Business Profile API (Fase 3)

## Prerequisito
Agentes 01-06 completados y estables. Al menos 20 clientes activos en plan Multi. OAuth de Google configurado en Google Cloud Console.

## Objetivo
Los usuarios del plan Multi pueden publicar sus respuestas directamente en Google Maps con un solo botón desde Telegram, sin tener que abrir el navegador ni el panel de Google. Es el diferenciador más potente de Revio y el principal argumento de venta del plan Multi.

---

## Flujo completo de publicación

```
1. Revio detecta reseña negativa en Google Maps
2. Bot envía alerta a Telegram con borrador de respuesta
3. Mensaje incluye tres botones inline:
   [✅ Publicar en Google] [✏️ Editar borrador] [❌ Descartar]

4a. Si pulsa [✅ Publicar en Google]:
    → Revio llama a GBP API con el borrador
    → Respuesta publicada en Google en <10 segundos
    → Bot confirma: "✅ Respuesta publicada en Google Maps"

4b. Si pulsa [✏️ Editar borrador]:
    → Bot pide el texto editado
    → Usuario escribe su versión
    → Bot muestra botones: [✅ Publicar este texto] [❌ Cancelar]

4c. Si pulsa [❌ Descartar]:
    → La alerta se marca como vista, sin publicar nada
```

---

## Setup de Google Business Profile API (una sola vez)

### En Google Cloud Console
```bash
# 1. En el mismo proyecto "Revio" de Google Cloud
# 2. Activar: My Business Account Management API
#    Y también: My Business Reviews API  (si está disponible separada)
# 3. Crear credenciales OAuth 2.0:
#    Tipo: Aplicación web
#    URI de redirección autorizado: https://api.tudominio.com/auth/google/callback
# 4. Guardar CLIENT_ID y CLIENT_SECRET
```

Variables de entorno nuevas:
```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://api.tudominio.com/auth/google/callback
```

### Ampliación del modelo Business (migración Alembic)
```sql
ALTER TABLE businesses ADD COLUMN gbp_location_name VARCHAR;
ALTER TABLE businesses ADD COLUMN gbp_access_token TEXT;
ALTER TABLE businesses ADD COLUMN gbp_refresh_token TEXT;
ALTER TABLE businesses ADD COLUMN gbp_token_expires_at TIMESTAMPTZ;
ALTER TABLE businesses ADD COLUMN auto_publish_positive BOOLEAN DEFAULT FALSE;
```

---

## Tareas en orden

### 1. Flujo OAuth para vincular Google Business Profile

**Comando /vincular-google en el bot:**
```python
# Handler protegido (plan Multi)
# Genera URL de autorización OAuth de Google con scopes:
# - https://www.googleapis.com/auth/business.manage
# Envía el link al usuario para que autorice en el navegador
```

**Endpoint callback (app/webhooks/google_oauth.py):**
```python
@app.get("/auth/google/callback")
async def google_oauth_callback(code: str, state: str):
    # state contiene el business_id firmado para saber a qué negocio vincular
    # Intercambiar code por access_token + refresh_token
    # Guardar tokens en businesses.gbp_access_token / gbp_refresh_token
    # Redirigir a página de confirmación o enviar mensaje al bot
```

### 2. Cliente GBP (app/integrations/google_business_profile.py)

```python
class GoogleBusinessProfileClient:
    async def reply_to_review(
        self,
        location_name: str,    # formato: accounts/{account}/locations/{location}
        review_id: str,        # ID de la reseña en Google
        reply_text: str,
        access_token: str,
    ) -> bool:
        """
        Publica una respuesta a una reseña en Google Maps.
        Endpoint: PUT https://mybusiness.googleapis.com/v4/{locationName}/reviews/{reviewId}/reply
        Devuelve True si fue exitoso, False si falló.
        """

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, datetime]:
        """
        Refresca el access_token usando el refresh_token.
        Los access_tokens de Google expiran en 1 hora.
        Devuelve (nuevo_access_token, nueva_fecha_expiración).
        """

    async def get_location_name(self, access_token: str) -> str | None:
        """
        Obtiene el location_name del negocio vinculado.
        Necesario para todas las llamadas a la API.
        """
```

### 3. Servicio de publicación (app/services/publish_service.py)

```python
async def publish_reply(business_id: int, user_id: int, review_id: int, text: str) -> bool:
    """
    Verifica que el negocio tiene GBP vinculado.
    Refresca el token si está próximo a expirar (< 5 min).
    Llama a GBPClient.reply_to_review().
    Guarda en alerts_log: published_at, published_text.
    """
```

### 4. Callback handler para botones inline

```python
# app/bot/handlers/publish_callback.py
# Maneja los tres botones: publicar / editar / descartar
# Para "editar": abre un ConversationHandler esperando el texto editado
# Para "publicar": llama a publish_service.publish_reply()
# Para "descartar": marca la alerta como vista en BD

async def handle_publish_callback(update: Update, context):
    query = update.callback_query
    action, review_id = query.data.split(":")  # formato: "publish:123"

    if action == "publish":
        # Recuperar el borrador guardado en alerts_log
        # Llamar a publish_service.publish_reply()
        await query.answer("✅ Publicando en Google...")

    elif action == "edit":
        await query.answer()
        await query.message.reply_text("Escribe el texto de respuesta que quieres publicar:")
        return WAITING_EDITED_TEXT   # estado del ConversationHandler

    elif action == "discard":
        await query.answer("Descartado")
        await query.message.edit_reply_markup(reply_markup=None)
```

### 5. Auto-publicación de positivas (opcional por negocio)

Para negocios con `auto_publish_positive = True` (configurable en /config):
- En el resumen diario, en vez de botón "Publicar", publicar automáticamente sin confirmación
- Solo para reseñas de 5★ (las de 4★ siempre piden confirmación)
- Enviar notificación: "✅ Respuesta publicada automáticamente en Google para {N} reseñas de 5★"

Esto convierte el resumen diario en un sistema completamente automatizado para las mejores reseñas.

### 6. Actualizar alerts_log (migración Alembic)

```sql
ALTER TABLE alerts_log ADD COLUMN published_at TIMESTAMPTZ;
ALTER TABLE alerts_log ADD COLUMN published_text TEXT;
ALTER TABLE alerts_log ADD COLUMN publish_status VARCHAR DEFAULT 'pending';
-- pending | published | discarded | failed
```

---

## Consideraciones importantes

**Límites de la API:** Google Business Profile API permite publicar respuestas pero tiene rate limits. Implementar delay de 1 segundo entre publicaciones si hay varios negocios o varias reseñas.

**El negocio debe estar verificado:** La ficha de Google del negocio debe estar verificada (el proceso del código postal). Documentar esto como requisito en el onboarding del plan Multi. Añadir verificación en el flujo: si el negocio no está verificado, la API devuelve 403 → informar al usuario con instrucciones.

**Revocación de permisos:** El usuario puede revocar el acceso en cualquier momento desde su cuenta Google. Manejar el error 401 del token refrescado como "vinculación perdida" y notificar al usuario.

---

## Verificación

```bash
# Test de publicación con cuenta de Google real
python -c "
import asyncio
from app.integrations.google_business_profile import GoogleBusinessProfileClient
client = GoogleBusinessProfileClient()
# Usar tokens reales de una cuenta de prueba
success = asyncio.run(client.reply_to_review(
    location_name='accounts/ACCOUNT_ID/locations/LOCATION_ID',
    review_id='REVIEW_ID',
    reply_text='Muchas gracias por su visita. Esperamos verle pronto.',
    access_token='ACCESS_TOKEN_REAL'
))
print('Publicación exitosa:', success)
# Verificar en Google Maps que la respuesta aparece
"
```
