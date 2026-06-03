"""Diagnóstico: muestra qué reseñas devuelve Google Places para cada negocio.

Uso (dentro del contenedor):
    docker compose -f docker-compose.prod.yml exec app python scripts/diagnose_reviews.py
"""
import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.integrations.google_places import GooglePlacesClient
from app.models.business import Business


async def main() -> None:
    client = GooglePlacesClient()
    async with AsyncSessionLocal() as session:
        businesses = list((await session.execute(select(Business))).scalars().all())

    if not businesses:
        print("No hay negocios en la BD.")
        return

    print(f"Analizando {len(businesses)} negocio(s)...\n")

    for b in businesses:
        print(f"━━━ {b.name}  (place_id={b.google_place_id})")
        reviews = await client.get_reviews(b.google_place_id)
        if not reviews:
            print("   ⚠️  Google no devolvió NINGUNA reseña.\n")
            continue

        negatives = [r for r in reviews if r.get("rating", 0) <= 3]
        positives = [r for r in reviews if r.get("rating", 0) >= 4]
        print(f"   Total devueltas por Google: {len(reviews)}  "
              f"(🔴 {len(negatives)} negativas · 🌟 {len(positives)} positivas)")

        for r in reviews:
            rating = r.get("rating", "?")
            name = r.get("name", "SIN-ID")
            author = r.get("authorAttribution", {}).get("displayName", "?")
            text_src = r.get("originalText") or r.get("text") or {}
            text = text_src.get("text", "") if isinstance(text_src, dict) else str(text_src)
            tag = "🔴" if isinstance(rating, int) and rating <= 3 else "🌟"
            print(f"   {tag} {rating}★ · {author} · {text[:50]!r}")
            print(f"        id={name[-30:] if name != 'SIN-ID' else 'SIN-ID'}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
