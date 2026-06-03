import logging
from datetime import date, datetime, timezone

from app.config import settings
from app.database import AsyncSessionLocal
from app.integrations.google_places import GooglePlacesClient
from app.models.review import Review
from app.repositories import business_repo, review_repo

logger = logging.getLogger(__name__)

_places_client = GooglePlacesClient()


def _classify_review(rating: int) -> str:
    return "negative" if rating <= 3 else "positive"


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return "fecha desconocida"
    return dt.strftime("%d/%m/%Y")


def _build_negative_alert_free(business_name: str, review: Review) -> str:
    text_preview = f'"{review.text[:200]}"' if review.text else "(sin texto)"
    return (
        f"🔴 Nueva reseña negativa — {business_name}\n\n"
        f"⭐ {review.rating}/5 · {review.author_name} · {_format_date(review.published_at)}\n"
        f"📍 Google Maps\n\n"
        f"{text_preview}\n\n"
        f"💡 Responder rápido mejora tu posicionamiento en Google.\n"
        f"Contrata el plan Pro para recibir un borrador de respuesta listo para copiar."
    )


def _build_negative_alert_pro(business_name: str, review: Review) -> str:
    text_preview = f'"{review.text[:200]}"' if review.text else "(sin texto)"
    return (
        f"🔴 Nueva reseña negativa — {business_name}\n\n"
        f"⭐ {review.rating}/5 · {review.author_name} · {_format_date(review.published_at)}\n"
        f"📍 Google Maps\n\n"
        f"{text_preview}"
    )


def _build_daily_digest(business_name: str, reviews: list[Review]) -> str:
    top = reviews[:5]
    lines = []
    for r in top:
        stars = "⭐" * r.rating
        snippet = f'"{r.text[:80]}..."' if r.text and len(r.text) > 80 else (f'"{r.text}"' if r.text else "")
        lines.append(f"{stars} {r.author_name} · {snippet}")

    body = "\n".join(lines)
    extra = f"\ny {len(reviews) - 5} más." if len(reviews) > 5 else ""

    return (
        f"🌟 Resumen de hoy — {business_name}\n\n"
        f"Has recibido {len(reviews)} reseña(s) positiva(s):\n\n"
        f"{body}{extra}\n\n"
        f"💡 Responder a las buenas también mejora tu ranking en Google.\n"
        f"Usa /responder para ver borradores de respuesta."
    )


async def poll_all_businesses() -> None:
    """Poll Google Places for every active business and dispatch alerts."""
    from app.bot import get_application
    from app.repositories.alert_log_repo import create as create_alert_log

    logger.info("Iniciando ciclo de polling de reseñas")

    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_active(session)
        logger.info("Polling %d negocios activos", len(businesses))

        for business in businesses:
            user = business.user
            try:
                raw_reviews = await _places_client.get_reviews(business.google_place_id)
            except Exception:
                logger.exception("Error al obtener reseñas para business_id=%d", business.id)
                continue

            for raw in raw_reviews:
                review_id = raw.get("name", "")
                platform = "google"

                if await review_repo.exists(session, platform, review_id):
                    continue

                rating = raw.get("rating", 0)
                review_type = _classify_review(rating)
                text = raw.get("text", {}).get("text") if isinstance(raw.get("text"), dict) else raw.get("text")
                author = raw.get("authorAttribution", {}).get("displayName", "Anónimo")
                published_raw = raw.get("publishTime")
                published_at: datetime | None = None
                if published_raw:
                    try:
                        published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                review = await review_repo.create(
                    session,
                    business_id=business.id,
                    platform=platform,
                    review_id=review_id,
                    rating=rating,
                    text=text,
                    author=author,
                    reviewed_at=published_at,
                    review_type=review_type,
                )

                if review_type == "negative":
                    is_active_sub = user.sub_status == "active"
                    try:
                        bot_app = get_application()
                        if user.plan in ("pro", "multi") and is_active_sub:
                            msg = _build_negative_alert_pro(business.name, review)
                        else:
                            msg = _build_negative_alert_free(business.name, review)

                        sent = await bot_app.bot.send_message(
                            chat_id=user.telegram_user_id, text=msg
                        )
                        await create_alert_log(
                            session,
                            review_id=review.id,
                            telegram_message_id=sent.message_id,
                            alert_type="negative_immediate",
                        )
                    except Exception:
                        logger.exception(
                            "Error al enviar alerta negativa para review_id=%d user_id=%d",
                            review.id, user.id,
                        )

    logger.info("Ciclo de polling completado")


async def send_daily_digest() -> None:
    """Send the daily digest of positive reviews to Pro/Multi users."""
    from app.bot import get_application
    from app.repositories.user_repo import get_all_active_subscribers

    logger.info("Iniciando resumen diario de positivas")
    today = date.today()

    async with AsyncSessionLocal() as session:
        users = await get_all_active_subscribers(session)

        for user in users:
            if user.plan not in ("pro", "multi"):
                continue
            if user.sub_status != "active":
                continue
            if user.telegram_user_id is None:
                continue

            user_businesses = await business_repo.get_all_by_user(session, user.id)

            for business in user_businesses:
                if business.is_paused:
                    continue
                positives = await review_repo.get_undigested_positives(
                    session, business.id, user.id, today
                )
                if not positives:
                    continue

                msg = _build_daily_digest(business.name, positives)
                try:
                    bot_app = get_application()
                    await bot_app.bot.send_message(chat_id=user.telegram_user_id, text=msg)
                    await review_repo.mark_digest_sent(session, [r.id for r in positives])
                    logger.info(
                        "Resumen diario enviado a user_id=%d business_id=%d (%d positivas)",
                        user.id, business.id, len(positives),
                    )
                except Exception:
                    logger.exception(
                        "Error enviando resumen diario a user_id=%d business_id=%d",
                        user.id, business.id,
                    )

    logger.info("Resumen diario completado")
