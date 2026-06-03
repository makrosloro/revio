import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from app.database import AsyncSessionLocal
from app.repositories import user_repo

logger = logging.getLogger(__name__)


async def activar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /activar TOKEN")
        return
    await run_activar(update, context, token=context.args[0])


async def run_activar(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    telegram_user_id = update.effective_user.id

    async with AsyncSessionLocal() as session:
        user = await user_repo.get_by_activation_token(session, token)

        if not user:
            await update.effective_message.reply_text(
                "Token no válido. Revisa el email o usa /suscribir para obtener uno nuevo."
            )
            return

        if user.token_expires_at and user.token_expires_at < datetime.now(timezone.utc):
            await update.effective_message.reply_text(
                "El token ha caducado (válido 48h). Contacta con soporte para renovarlo."
            )
            return

        if user.telegram_user_id and user.telegram_user_id != telegram_user_id:
            await update.effective_message.reply_text(
                "Este token ya está vinculado a otra cuenta de Telegram."
            )
            return

        await user_repo.activate(session, user.id, telegram_user_id)

    await update.effective_message.reply_text(
        f"Cuenta activada correctamente. Plan: {user.plan.capitalize()}\n"
        "Usa /agregar para añadir tu primer negocio."
    )
    logger.info("User %s activated telegram_user_id %s", user.id, telegram_user_id)
