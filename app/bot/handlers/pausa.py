import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards import pause_keyboard
from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo

logger = logging.getLogger(__name__)


@require_subscription(min_plan="pro")
async def pausa(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> None:
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)

    active = [b for b in businesses if not b.is_paused]
    if not active:
        await update.message.reply_text("No tienes negocios activos para pausar.")
        return

    if len(active) == 1:
        async with AsyncSessionLocal() as session:
            await business_repo.toggle_pause(session, active[0].id, user.id, True)
        await update.message.reply_text(f"Alertas de '{active[0].name}' pausadas.")
        return

    await update.message.reply_text(
        "Selecciona el negocio que quieres pausar:",
        reply_markup=pause_keyboard(active),
    )


@require_subscription(min_plan="pro")
async def reanudar(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> None:
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)

    paused = [b for b in businesses if b.is_paused]
    if not paused:
        await update.message.reply_text("No tienes negocios pausados.")
        return

    if len(paused) == 1:
        async with AsyncSessionLocal() as session:
            await business_repo.toggle_pause(session, paused[0].id, user.id, False)
        await update.message.reply_text(f"Alertas de '{paused[0].name}' reanudadas.")
        return

    await update.message.reply_text(
        "Selecciona el negocio que quieres reanudar:",
        reply_markup=pause_keyboard(paused),
    )


async def handle_pause_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, business_id_str = query.data.split("_", 1)
    business_id = int(business_id_str)
    is_paused = action == "pause"
    telegram_user_id = update.effective_user.id

    async with AsyncSessionLocal() as session:
        from app.repositories import user_repo
        user = await user_repo.get_by_telegram_id(session, telegram_user_id)
        if not user:
            await query.edit_message_text("Sesión expirada. Usa /pausa de nuevo.")
            return
        business = await business_repo.toggle_pause(session, business_id, user.id, is_paused)

    if not business:
        await query.edit_message_text("Negocio no encontrado.")
        return

    action_text = "pausadas" if is_paused else "reanudadas"
    await query.edit_message_text(f"Alertas de '{business.name}' {action_text}.")
    logger.info("Business %s %s by user %s", business_id, action, user.id)
