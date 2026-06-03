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


def _build_negative_alert_pro(business_name: str, review: Review, draft: str = "") -> str:
    text_preview = f'"{review.text[:200]}"' if review.text else "(sin texto)"
    draft_section = f"\n\n💬 Borrador de respuesta:\n{draft}" if draft else ""
    return (
        f"🔴 Nueva reseña negativa — {business_name}\n\n"
        f"⭐ {review.rating}/5 · {review.author_name} · {_format_date(review.published_at)}\n"
        f"📍 Google Maps\n\n"
        f"{text_preview}{draft_section}"
    )


def _build_daily_digest(
    business_name: str,
    reviews: list[Review],
    drafts: dict[int, str] | None = None,
) -> str:
    top = reviews[:5]
    drafts = drafts or {}
    lines = []
    for r in top:
        stars = "⭐" * r.rating
        snippet = f'"{r.text[:100]}..."' if r.text and len(r.text) > 100 else (f'"{r.text}"' if r.text else "")
        lines.append(f"{stars} {r.author_name}\n{snippet}")
        if r.id in drafts:
            lines.append(f"💬 Borrador: {drafts[r.id]}")
        lines.append("")

    body = "\n".join(lines).rstrip()
    extra = f"\ny {len(reviews) - 5} más." if len(reviews) > 5 else ""

    return (
        f"🌟 Resumen de hoy — {business_name}\n\n"
        f"Has recibido {len(reviews)} reseña(s) positiva(s):\n\n"
        f"{body}{extra}\n\n"
        f"Usa /responder para regenerar cualquier borrador."
    )


async def poll_all_businesses() -> None:
    """Poll Google Places for every active business and dispatch alerts."""
    from app.bot import get_application
    from app.integrations.anthropic_client import get_anthropic_client
    from app.repositories.alert_log_repo import create as create_alert_log

    logger.info("Iniciando ciclo de polling de reseñas")
    anthropic = get_anthropic_client()

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
                        draft = ""
                        draft_tokens = 0
                        if user.plan in ("pro", "multi") and is_active_sub:
                            draft, draft_tokens = await anthropic.generate_negative_draft(
                                review, business
                            )
                            msg = _build_negative_alert_pro(business.name, review, draft)
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
                            draft_type="negative" if draft else None,
                            ai_draft_tokens=draft_tokens if draft_tokens else None,
                        )
                    except Exception:
                        logger.exception(
                            "Error al enviar alerta negativa para review_id=%d user_id=%d",
                            review.id, user.id,
                        )

    logger.info("Ciclo de polling completado")


async def send_daily_digest() -> None:
    """Send the daily digest of positive reviews with AI drafts to Pro/Multi users."""
    from app.bot import get_application
    from app.integrations.anthropic_client import get_anthropic_client
    from app.repositories.user_repo import get_all_active_subscribers

    logger.info("Iniciando resumen diario de positivas")
    today = date.today()
    anthropic = get_anthropic_client()

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

                # Generate drafts for up to 5 reviews to control costs
                drafts: dict[int, str] = {}
                for r in positives[:5]:
                    draft, _ = await anthropic.generate_positive_draft(r, business)
                    if draft:
                        drafts[r.id] = draft

                msg = _build_daily_digest(business.name, positives, drafts)
                try:
                    bot_app = get_application()
                    await bot_app.bot.send_message(chat_id=user.telegram_user_id, text=msg)
                    await review_repo.mark_digest_sent(session, [r.id for r in positives])
                    logger.info(
                        "Resumen diario enviado a user_id=%d business_id=%d (%d positivas, %d borradores)",
                        user.id, business.id, len(positives), len(drafts),
                    )
                except Exception:
                    logger.exception(
                        "Error enviando resumen diario a user_id=%d business_id=%d",
                        user.id, business.id,
                    )

    logger.info("Resumen diario completado")
