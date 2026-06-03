---
name: tests
description: Usar para crear o ampliar la infraestructura de tests — conftest.py, fixtures base, y tests unitarios de cada módulo. Ejecutar después del agente 01 (infraestructura) y antes o en paralelo con los demás agentes.
---

# Agente 08 — Infraestructura de Tests

## Prerequisito
Agente 01 completado. Los modelos SQLAlchemy existen. `requirements.txt` incluye `pytest pytest-asyncio httpx faker`.

## Objetivo
Crear `tests/conftest.py` con todos los fixtures reutilizables y los primeros tests unitarios de cada capa. El CI debe pasar con cobertura real, no con una suite vacía.

## Dependencias adicionales

Añadir a `requirements.txt`:
```
pytest
pytest-asyncio
pytest-cov
httpx                 # para TestClient de FastAPI
faker                 # datos de prueba realistas
aiosqlite             # SQLite async para tests (sin necesidad de PostgreSQL)
```

## Tareas en orden

### 1. tests/conftest.py — Fixtures base

Crear con los siguientes fixtures. Todos son `scope="function"` salvo que se indique.

**Base de datos de test (SQLite en memoria):**
```python
@pytest.fixture
async def db_session():
    """
    Sesión de BD aislada por test. Usa SQLite en memoria.
    Más rápido que PostgreSQL y sin dependencias externas.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()
```

**Usuario de test:**
```python
@pytest.fixture
async def test_user(db_session):
    """Usuario con suscripción Pro activa, telegram_user_id vinculado."""
    user = User(
        email="test@example.com",
        telegram_user_id=123456789,
        stripe_customer_id="cus_test123",
        stripe_sub_id="sub_test123",
        plan="pro",
        sub_status="active",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def test_user_free(db_session):
    """Usuario con plan gratuito, sin suscripción activa."""
    # Misma estructura, plan="free", sub_status="inactive"
```

**Negocio de test:**
```python
@pytest.fixture
async def test_business(db_session, test_user):
    """Negocio activo vinculado al test_user."""
    business = Business(
        user_id=test_user.id,
        name="Restaurante Test",
        google_place_id="ChIJtest123",
        active=True,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business
```

**Mock Google Places (con ambos tipos de reseña):**
```python
@pytest.fixture
def mock_google_places():
    """Mock con mezcla de reseñas negativas y positivas."""
    with patch("app.integrations.google_places.GooglePlacesClient") as mock:
        instance = mock.return_value
        instance.get_reviews = AsyncMock(return_value=[
            {"review_id": "neg_001", "rating": 2, "text": "Servicio muy lento.", "author": "María G.", "reviewed_at": datetime.utcnow()},
            {"review_id": "pos_001", "rating": 5, "text": "Excelente, volveremos.", "author": "Carlos L.", "reviewed_at": datetime.utcnow()},
            {"review_id": "pos_002", "rating": 4, "text": "Muy buena experiencia.", "author": "Ana M.", "reviewed_at": datetime.utcnow()},
        ])
        yield instance

@pytest.fixture
def mock_telegram_bot():
    """Mock del bot de Telegram. Captura todos los mensajes enviados."""
    with patch("app.bot.handlers.get_bot") as mock:
        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
        bot.send_document = AsyncMock(return_value=MagicMock(message_id=2))
        mock.return_value = bot
        yield bot

@pytest.fixture
def mock_stripe():
    """Mock de Stripe. Simula eventos de webhook exitosos."""
    with patch("stripe.Webhook.construct_event") as mock_event, \
         patch("stripe.checkout.Session.create") as mock_session:
        mock_session.return_value = MagicMock(url="https://checkout.stripe.com/test")
        yield {"event": mock_event, "session": mock_session}

@pytest.fixture
def mock_anthropic():
    """Mock del cliente de Anthropic. Devuelve borrador de respuesta fijo."""
    with patch("app.integrations.anthropic_client.AnthropicClient") as mock:
        instance = mock.return_value
        instance.generate_reply_draft = AsyncMock(
            return_value="Estimado cliente, lamentamos su experiencia. "
                         "Por favor, contáctenos para resolverlo."
        )
        yield instance
```

**Cliente de test para FastAPI:**
```python
@pytest.fixture
async def client(db_session):
    """Cliente HTTP para tests de endpoints FastAPI."""
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

### 2. Tests de repositorios (tests/test_repositories/)

**test_user_repo.py** — Cubrir:
- `get_by_telegram_id` devuelve user correcto y None si no existe
- `get_by_activation_token` devuelve None si token expirado
- `activate` vincula el telegram_user_id y borra el token
- `update_subscription_status` actualiza correctamente

**test_business_repo.py** — Cubrir:
- `get_by_id` con user_id correcto devuelve negocio
- `get_by_id` con user_id incorrecto devuelve None (aislamiento crítico)
- `get_all_active` no devuelve negocios de otros usuarios

**test_review_repo.py** — Cubrir:
- `exists` devuelve True solo si platform + review_id coinciden
- `create` guarda todos los campos correctamente
- `get_recent_by_business` respeta el filtro de user_id

### 3. Tests de servicios (tests/test_services/)

**test_review_service.py** — Cubrir:
- `poll_all_businesses` llama a GooglePlaces una vez por negocio activo
- Reseña ya existente no genera alerta duplicada
- Reseña nueva con rating ≤ 3 → `review_type = negative` → alerta inmediata (1 llamada a `bot.send_message`)
- Reseña nueva con rating ≥ 4 → `review_type = positive` → NO alerta inmediata (0 llamadas)
- `send_daily_digest` envía resumen solo si hay positivas sin enviar en el día
- `send_daily_digest` no envía nada si todas las positivas ya tienen `digest_sent_at`
- Usuario plan Free con reseña negativa → alerta sin borrador
- Fallo de GooglePlaces no bloquea el polling de los otros negocios

### 4. Tests del middleware (tests/test_bot/)

**test_middleware.py** — Cubrir:
- Usuario sin telegram_user_id registrado → respuesta de "activa tu cuenta"
- Usuario con sub_status="cancelled" → respuesta de "suscripción no activa"
- Usuario con plan="free" intentando comando Pro → respuesta de "plan insuficiente"
- Usuario con plan="pro" en comando Pro → handler se ejecuta (user inyectado)

### 5. Tests del webhook de Stripe (tests/test_webhooks/)

**test_stripe.py** — Cubrir:
- `checkout.session.completed` → user creado + token generado
- `checkout.session.completed` con email existente → user actualizado, no duplicado
- `customer.subscription.deleted` → sub_status = "cancelled"
- Firma inválida → HTTP 400, no se procesa nada

### 6. pyproject.toml — Configuración de pytest

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = [
    "ignore::DeprecationWarning",
    "ignore::pytest.PytestUnraisableExceptionWarning",
]

[tool.coverage.run]
source = ["app"]
omit = ["app/migrations/*", "tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

## Criterio de cobertura mínima

El CI no debe exigir un % arbitrario de cobertura sino que los tests cubran los caminos críticos:

- Aislamiento de datos (user_id siempre filtrado): **obligatorio**
- Middleware de autenticación: **obligatorio**
- Webhook de Stripe: **obligatorio**
- Polling sin duplicados: **obligatorio**
- Generación de alertas (rating ≤ 3): **obligatorio**

## Verificación

```bash
pytest tests/ -v --tb=short
# Todos los tests deben pasar

pytest tests/ --cov=app --cov-report=term-missing
# Los módulos críticos deben aparecer con cobertura > 80%

# Test específico del aislamiento de datos (el más importante)
pytest tests/test_repositories/test_business_repo.py::test_get_by_id_wrong_user_returns_none -v
# MUST PASS
```
