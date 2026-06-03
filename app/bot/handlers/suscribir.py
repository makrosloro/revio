import asyncio
import logging

import stripe
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards import subscription_keyboard
from app.config import settings

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


async def suscribir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Elige tu plan:\n\n"
        "Pro (29€/mes) — 1 negocio, alertas inmediatas, borradores IA\n"
        "Multi (59€/mes) — hasta 3 negocios + publicación directa en Google",
        reply_markup=subscription_keyboard(),
    )


async def handle_subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    plan = "pro" if query.data == "subscribe_pro" else "multi"
    price_id = settings.STRIPE_PRO_PRICE_ID if plan == "pro" else settings.STRIPE_MULTI_PRICE_ID
    telegram_user_id = update.effective_user.id

    try:
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.WEBHOOK_URL}/payment/success",
            cancel_url=f"{settings.WEBHOOK_URL}/payment/cancel",
            metadata={"telegram_user_id": str(telegram_user_id), "plan": plan},
        )
        await query.edit_message_text(
            f"Plan {plan.capitalize()} seleccionado.\n\n"
            f"Completa el pago aquí:\n{session.url}\n\n"
            "Tras el pago recibirás un email con tu token de activación."
        )
    except Exception:
        logger.exception("Error creating Stripe checkout session")
        await query.edit_message_text(
            "Error al crear el enlace de pago. Inténtalo de nuevo en unos minutos."
        )
