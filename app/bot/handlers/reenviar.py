import asyncio
import logging
import re

import stripe
from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import user_repo
from app.services.email_service import send_activation_email

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Generic reply — never reveals whether an email exists (avoids account probing)
_GENERIC_OK = (
    "Si existe una suscripción activa con ese email, te hemos enviado un correo "
    "con un nuevo enlace de activación. Revisa también la carpeta de spam."
)


async def reenviar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Uso: /reenviar tu@email.com\n\n"
            "Te enviaremos un nuevo enlace de activación si tienes una suscripción activa."
        )
        return

    email = context.args[0].strip().lower()
    if not _EMAIL_RE.match(email):
        await update.message.reply_text("Ese email no parece válido. Revisa e inténtalo de nuevo.")
        return

    try:
        token = await _resolve_token(email)
    except Exception:
        logger.exception("Error in /reenviar for email")
        await update.message.reply_text(
            "Algo fue mal. Inténtalo de nuevo en unos minutos."
        )
        return

    if token:
        await send_activation_email(email, token)
        logger.info("Resent activation email")

    # Always the same reply regardless of outcome
    await update.message.reply_text(_GENERIC_OK)


async def _resolve_token(email: str) -> str | None:
    """Return a fresh activation token for the email, or None if no active sub exists."""
    async with AsyncSessionLocal() as session:
        user = await user_repo.get_by_email(session, email)

        # Case 1 — user already in our DB but not yet activated
        if user:
            if user.telegram_user_id is not None:
                # Already activated — nothing to resend
                return None
            return await user_repo.refresh_activation_token(session, user.id)

    # Case 2 — not in our DB: look up an active subscription in Stripe
    plan, customer_id, sub_id = await _find_stripe_subscription(email)
    if not sub_id:
        return None

    async with AsyncSessionLocal() as session:
        # Re-check inside the new session to avoid a race
        user = await user_repo.get_by_email(session, email)
        if user:
            if user.telegram_user_id is not None:
                return None
            return await user_repo.refresh_activation_token(session, user.id)
        new_user = await user_repo.create_from_stripe(
            session, email=email, stripe_customer_id=customer_id,
            stripe_sub_id=sub_id, plan=plan,
        )
        return new_user.activation_token


async def _find_stripe_subscription(email: str) -> tuple[str, str | None, str | None]:
    """Look up an active Stripe subscription by email. Returns (plan, customer_id, sub_id)."""
    customers = await asyncio.to_thread(stripe.Customer.list, email=email, limit=1)
    if not customers.data:
        return "pro", None, None

    customer = customers.data[0]
    subs = await asyncio.to_thread(
        stripe.Subscription.list, customer=customer.id, status="active", limit=1
    )
    if not subs.data:
        return "pro", None, None

    sub = subs.data[0]
    price_id = sub["items"]["data"][0]["price"]["id"] if sub["items"]["data"] else None
    if price_id == settings.STRIPE_MULTI_PRICE_ID:
        plan = "multi"
    else:
        plan = "pro"
    return plan, customer.id, sub.id
