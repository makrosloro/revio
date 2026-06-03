import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from app.database import AsyncSessionLocal
from app.repositories import user_repo

logger = logging.getLogger(__name__)

PLANS = ["free", "pro", "multi"]


def require_subscription(min_plan: str = "pro"):
    """Decorator that blocks access based on subscription plan and status."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, **kwargs):
            telegram_user_id = update.effective_user.id
            async with AsyncSessionLocal() as session:
                user = await user_repo.get_by_telegram_id(session, telegram_user_id)

            if not user:
                await update.effective_message.reply_text(
                    "Tu cuenta no está activada.\n"
                    "Usa /activar TOKEN con el token que recibiste por email."
                )
                return

            if user.sub_status not in ("active", "trialing"):
                await update.effective_message.reply_text(
                    "Tu suscripción no está activa.\n"
                    "Usa /suscribir para renovarla."
                )
                return

            if PLANS.index(user.plan) < PLANS.index(min_plan):
                await update.effective_message.reply_text(
                    f"Este comando requiere el plan {min_plan.capitalize()}.\n"
                    "Usa /suscribir para mejorar tu plan."
                )
                return

            kwargs["user"] = user
            return await func(update, context, **kwargs)

        return wrapper
    return decorator
