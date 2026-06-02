# Convenciones Python — NegocioSano

Aplicar en todos los archivos `.py` del proyecto.

## Estilo
- Python 3.11+. Type hints en todas las funciones. Ninguna función sin return type.
- snake_case para funciones y variables. PascalCase para clases. UPPER_SNAKE_CASE para constantes.
- Líneas máximo 100 caracteres. Imports ordenados: stdlib → terceros → internos.
- Docstring en clases y funciones públicas (una línea es suficiente).

## Async
- Toda función que haga IO (BD, HTTP, Telegram) es `async def`.
- Nunca usar `asyncio.run()` dentro de handlers o servicios — solo en scripts de prueba.
- Usar `asyncio.gather()` para paralelizar cuando tenga sentido (ej: polling de varios negocios).

## Errores
- Nunca capturar `Exception` genérico sin loguear el error completo con `logger.exception()`.
- Los servicios capturan errores de integración (HTTP, BD) y devuelven None o lista vacía — nunca propagan excepciones a los handlers del bot.
- Los handlers del bot nunca lanzan excepciones — siempre responden algo al usuario.

## Logging
- Usar `logging` estándar. Logger por módulo: `logger = logging.getLogger(__name__)`.
- Niveles: DEBUG para datos de polling, INFO para eventos importantes, WARNING para fallos recuperables, ERROR para fallos que necesitan atención.
- Nunca loguear tokens, API keys, textos de reseñas completos ni datos personales.

## Tests
- Un test por función pública en `tests/`. Usar `pytest-asyncio` para tests async.
- Mockear todas las llamadas externas (Google API, Stripe, Telegram, Anthropic) con `unittest.mock.AsyncMock`.
- Nombre de tests: `test_<función>_<escenario>` (ej: `test_get_reviews_returns_empty_on_404`).
