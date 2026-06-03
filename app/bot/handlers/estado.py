import asyncio
import logging
from datetime import datetime, timezone

import stripe
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.middleware import require_subscription
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@require_subscription(min_plan="free")
async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> None:
    async with AsyncSessionLocal() as session:
        count = await business_repo.count_by_user(session, user.id)

    renewal_text = "—"
    if user.stripe_subscription_id:
        try:
            sub = await asyncio.to_thread(
                stripe.Subscription.retrieve, user.stripe_subscription_id
            )
            renewal_dt = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc)
            renewal_text = renewal_dt.strftime("%d/%m/%Y")
        except Exception:
            logger.warning("Could not retrieve Stripe subscription for user %s", user.id)

    await update.message.reply_text(
        f"Estado de tu cuenta:\n\n"
        f"Plan: {user.plan.capitalize()}\n"
        f"Suscripción: {user.sub_status}\n"
        f"Próxima renovación: {renewal_text}\n"
        f"Negocios monitorizados: {count}"
    )
