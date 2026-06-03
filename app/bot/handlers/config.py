import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo

logger = logging.getLogger(__name__)

_TONES = {
    "cercano": "😊 Cercano",
    "profesional": "💼 Profesional",
    "formal": "🎩 Formal",
}


@require_subscription(min_plan="pro")
async def config_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None
) -> None:
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)

    if not businesses:
        await update.message.reply_text(
            "Aún no tienes negocios añadidos.\n"
            "Usa /agregar para añadir tu primer negocio."
        )
        return

    rows = []
    lines = ["*Tus negocios monitorizados:*\n"]
    for i, b in enumerate(businesses, 1):
        status = "⏸ Pausado" if b.is_paused else "▶ Activo"
        tone_label = _TONES.get(b.tone or "cercano", b.tone or "cercano")
        lines.append(f"{i}. {b.name} — {status} · Tono: {tone_label}")
        rows.append([
            InlineKeyboardButton(
                f"🎭 Cambiar tono — {b.name}",
                callback_data=f"cfg_tone_{b.id}",
            )
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def handle_config_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    from app.repositories import user_repo as urepo

    async with AsyncSessionLocal() as session:
        user = await urepo.get_by_telegram_id(session, update.effective_user.id)

    if not user:
        await query.edit_message_text("Cuenta no activada. Usa /activar TOKEN.")
        return

    if data.startswith("cfg_tone_"):
        try:
            business_id = int(data[len("cfg_tone_"):])
        except ValueError:
            return
        await _show_tone_options(query, user, business_id)

    elif data.startswith("cfg_set_tone_"):
        parts = data[len("cfg_set_tone_"):].split("_", 1)
        if len(parts) != 2:
            return
        try:
            business_id = int(parts[0])
        except ValueError:
            return
        new_tone = parts[1]
        if new_tone not in _TONES:
            return
        await _save_tone(query, user, business_id, new_tone)


async def _show_tone_options(query, user: User, business_id: int) -> None:
    async with AsyncSessionLocal() as session:
        business = await business_repo.get_by_id(session, business_id, user.id)

    if not business:
        await query.edit_message_text("Negocio no encontrado.")
        return

    rows = [
        [InlineKeyboardButton(label, callback_data=f"cfg_set_tone_{business_id}_{key}")]
        for key, label in _TONES.items()
    ]
    await query.edit_message_text(
        f"Elige el tono de respuesta para *{business.name}*:\n\n"
        "El tono afecta a los borradores generados por IA.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def _save_tone(query, user: User, business_id: int, tone: str) -> None:
    from sqlalchemy import update as sa_update
    from app.models.business import Business

    async with AsyncSessionLocal() as session:
        business = await business_repo.get_by_id(session, business_id, user.id)
        if not business:
            await query.edit_message_text("Negocio no encontrado.")
            return
        business.tone = tone
        await session.commit()

    label = _TONES[tone]
    await query.edit_message_text(
        f"✅ Tono actualizado a *{label}* para *{business.name}*.\n\n"
        "Los próximos borradores usarán este tono.",
        parse_mode="Markdown",
    )
