import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo, review_repo

logger = logging.getLogger(__name__)


@require_subscription(min_plan="pro")
async def responder(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None
) -> None:
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)
        if not businesses:
            await update.message.reply_text(
                "No tienes negocios añadidos. Usa /agregar."
            )
            return

        rows = []
        for business in businesses:
            recents = await review_repo.get_recent_negatives(
                session, business.id, user.id, limit=5
            )
            for r in recents:
                snippet = (r.text or "")[:40].replace("\n", " ")
                label = f"⭐{r.rating} {r.author_name} — {snippet}…"
                rows.append([InlineKeyboardButton(label, callback_data=f"resp_sel_{r.id}")])

    if not rows:
        await update.message.reply_text(
            "No hay reseñas negativas recientes para responder. ¡Buen trabajo! 👌"
        )
        return

    keyboard = InlineKeyboardMarkup(rows[:5])
    await update.message.reply_text(
        "Selecciona una reseña para generar un borrador de respuesta:",
        reply_markup=keyboard,
    )


async def handle_responder_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    from app.repositories import user_repo as urepo

    async with AsyncSessionLocal() as session:
        user = await urepo.get_by_telegram_id(session, update.effective_user.id)

    if not user or user.plan not in ("pro", "multi"):
        await query.edit_message_text("Esta función requiere el plan Pro.")
        return

    if data.startswith("resp_sel_") or data.startswith("resp_regen_"):
        prefix = "resp_sel_" if data.startswith("resp_sel_") else "resp_regen_"
        try:
            review_id = int(data[len(prefix):])
        except ValueError:
            await query.edit_message_text("Reseña no encontrada.")
            return
        await _generate_and_show(query, user, review_id)

    elif data == "resp_ok":
        await query.edit_message_text("✅ Borrador guardado. ¡Puedes pegarlo en Google!")


async def _generate_and_show(query, user: User, review_id: int) -> None:
    from app.integrations.anthropic_client import get_anthropic_client

    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)
        business_map = {b.id: b for b in businesses}

        review = None
        business = None
        for biz in businesses:
            candidates = await review_repo.get_recent_negatives(
                session, biz.id, user.id, limit=20
            )
            for r in candidates:
                if r.id == review_id:
                    review = r
                    business = biz
                    break
            if review:
                break

    if not review or not business:
        await query.edit_message_text("Reseña no encontrada o ya no disponible.")
        return

    await query.edit_message_text("⏳ Generando borrador…")

    anthropic = get_anthropic_client()
    draft, _ = await anthropic.generate_draft_on_demand(review, business)

    if not draft:
        await query.edit_message_text(
            "No se pudo generar el borrador. Inténtalo de nuevo con /responder."
        )
        return

    snippet = (review.text or "")[:120]
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Regenerar", callback_data=f"resp_regen_{review_id}"),
            InlineKeyboardButton("✅ Listo", callback_data="resp_ok"),
        ]
    ])

    await query.edit_message_text(
        f"⭐ {review.rating}/5 · {review.author_name}\n"
        f'"{snippet}{"…" if len(review.text or "") > 120 else ""}"\n\n'
        f"💬 Borrador de respuesta:\n{draft}",
        reply_markup=keyboard,
    )
