import logging
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo, review_repo

logger = logging.getLogger(__name__)

PLANS = ["free", "pro", "multi"]


def _resenas_keyboard(user_plan: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🔴 Ver negativas recientes", callback_data="resenas_negativas")],
    ]
    if user_plan in ("pro", "multi"):
        rows.append(
            [InlineKeyboardButton("🌟 Ver positivas de hoy", callback_data="resenas_positivas")]
        )
    return InlineKeyboardMarkup(rows)


@require_subscription(min_plan="free")
async def resenas(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> None:
    keyboard = _resenas_keyboard(user.plan)
    await update.message.reply_text(
        "¿Qué reseñas quieres ver?", reply_markup=keyboard
    )


async def handle_resenas_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    from app.repositories import user_repo as urepo

    async with AsyncSessionLocal() as session:
        user = await urepo.get_by_telegram_id(session, update.effective_user.id)

    if not user:
        await query.edit_message_text("Cuenta no activada. Usa /activar TOKEN.")
        return

    if query.data == "resenas_negativas":
        await _show_negatives(query, user)
    elif query.data == "resenas_positivas":
        if user.plan not in ("pro", "multi"):
            await query.edit_message_text(
                "Esta opción requiere el plan Pro o Multi. Usa /suscribir para mejorar tu plan."
            )
            return
        await _show_today_positives(query, user)


async def _show_negatives(query, user: User) -> None:
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)
        if not businesses:
            await query.edit_message_text("No tienes negocios añadidos. Usa /agregar.")
            return

        lines = []
        for business in businesses:
            reviews = await review_repo.get_recent_negatives(session, business.id, user.id, limit=5)
            if not reviews:
                continue
            lines.append(f"*{business.name}*")
            for r in reviews:
                snippet = f'"{r.text[:80]}..."' if r.text and len(r.text) > 80 else (f'"{r.text}"' if r.text else "")
                lines.append(f"  ⭐ {r.rating}/5 · {r.author_name} · {snippet}")

    if not lines:
        await query.edit_message_text("No hay reseñas negativas recientes.")
        return

    await query.edit_message_text(
        "🔴 *Reseñas negativas recientes:*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def _show_today_positives(query, user: User) -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)
        if not businesses:
            await query.edit_message_text("No tienes negocios añadidos. Usa /agregar.")
            return

        lines = []
        for business in businesses:
            reviews = await review_repo.get_undigested_positives(
                session, business.id, user.id, today
            )
            if not reviews:
                continue
            lines.append(f"*{business.name}*")
            for r in reviews:
                stars = "⭐" * r.rating
                snippet = f'"{r.text[:80]}..."' if r.text and len(r.text) > 80 else (f'"{r.text}"' if r.text else "")
                lines.append(f"  {stars} {r.author_name} · {snippet}")

    if not lines:
        await query.edit_message_text("No hay reseñas positivas nuevas hoy.")
        return

    await query.edit_message_text(
        "🌟 *Positivas de hoy (sin responder):*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )
