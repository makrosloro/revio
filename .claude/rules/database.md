# Reglas de Base de Datos — NegocioSano

## Aislamiento multi-tenant — CRÍTICO

**Regla absoluta:** toda query que devuelva `Business`, `Review` o `AlertLog` DEBE incluir el filtro `user_id`. Sin excepción.

```python
# ✅ CORRECTO
async def get_business(business_id: int, user_id: int) -> Business | None:
    result = await session.execute(
        select(Business).where(
            Business.id == business_id,
            Business.user_id == user_id  # ← SIEMPRE
        )
    )
    return result.scalar_one_or_none()

# ❌ INCORRECTO — permite acceso cruzado entre usuarios
async def get_business(business_id: int) -> Business | None:
    result = await session.execute(select(Business).where(Business.id == business_id))
    return result.scalar_one_or_none()
```

Nunca hacer queries directas en handlers — siempre a través del repositorio correspondiente.

## Convenciones de BD
- Nombres de tablas y columnas: `snake_case` siempre.
- Toda tabla tiene `id SERIAL PRIMARY KEY` y `created_at TIMESTAMPTZ DEFAULT now()`.
- FKs siempre con `ON DELETE CASCADE` cuando el hijo no tiene sentido sin el padre.
- Índices: crear índice en toda columna usada en WHERE frecuentemente (`telegram_user_id`, `stripe_sub_id`, `google_place_id`, `platform + review_id`).

## Migrations
- Nunca `Base.metadata.create_all()` fuera de tests.
- Toda modificación de esquema pasa por `alembic revision --autogenerate`.
- Revisar el fichero generado antes de hacer `alembic upgrade head` — Alembic a veces genera migraciones incorrectas con columnas nullable.
- Nombre descriptivo en cada revisión: `alembic revision --autogenerate -m "add_tone_to_businesses"`.

## Transacciones
- Usar `async with session.begin()` para operaciones que modifican múltiples tablas.
- Si una parte falla, el rollback es automático.
