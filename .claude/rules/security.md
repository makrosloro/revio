# Reglas de Seguridad — NegocioSano

## Secretos
- Ningún secreto en el código fuente ni en el historial de git.
- `.env` en `.gitignore`. Solo `.env.example` en el repositorio.
- En producción: cargar desde variables de entorno del contenedor Docker.
- Si accidentalmente se commitea un secreto: rotarlo inmediatamente antes de cualquier otra acción.

## Webhooks
- El webhook de Stripe DEBE verificar la firma con `stripe.Webhook.construct_event()`. Si la verificación falla → HTTP 400, no procesar.
- El webhook de Telegram usa el path secreto `/{TELEGRAM_BOT_TOKEN}/webhook` — nunca exponer este path en documentación o logs.
- Todos los endpoints de webhook devuelven HTTP 200 rápido y procesan en background para no hacer timeout.

## Validación de inputs del bot
- Todo input de texto del usuario se sanitiza antes de guardarlo en BD: strip(), máximo 500 chars, sin HTML.
- Los links de Google Maps y TripAdvisor se validan con regex antes de procesar.
- Si un usuario envía un Place ID que no existe en Google → respuesta amigable, no exponer el error interno.
- Rate limiting en comandos costosos (/informe, /regenerar): máximo 1 vez por hora por usuario.

## Exposición de datos
- Nunca enviar `user.id`, `stripe_customer_id` ni IDs internos en mensajes de Telegram.
- Los mensajes de error al usuario son genéricos: "Algo fue mal, inténtalo en unos minutos". El detalle va al log interno.
- El admin (ADMIN_CHAT_ID) sí recibe mensajes con más detalle técnico para debugging.

## Cloudflare Tunnel
- La app nunca escucha en IP pública directamente. Todo el tráfico pasa por Cloudflare Tunnel.
- El endpoint `/webhook/stripe` y `/{TOKEN}/webhook` son los únicos endpoints expuestos externamente.
- `/health` y cualquier endpoint de debug solo accesible desde red local (127.0.0.1).
