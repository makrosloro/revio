import asyncio
import logging

import stripe
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import user_repo

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


def _plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 Plan Gratuito — 0€", callback_data="subscribe_free")],
        [InlineKeyboardButton("💼 Plan Pro — 29€/mes", callback_data="subscribe_pro")],
        [InlineKeyboardButton("🏢 Plan Multi — 59€/mes", callback_data="subscribe_multi")],
    ])


async def suscribir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Elige tu plan:\n\n"
        "🆓 *Gratuito* — 1 negocio · Google Maps · Alertas sin borrador\n\n"
        "💼 *Pro — 29€/mes* — 1 negocio · Alertas con borrador IA · Resumen diario\n\n"
        "🏢 *Multi — 59€/mes* — 3 negocios · Todo lo de Pro · Publicación en Google",
        parse_mode="Markdown",
        reply_markup=_plans_keyboard(),
    )


async def handle_subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    telegram_user_id = update.effective_user.id

    if query.data == "subscribe_free":
        async with AsyncSessionLocal() as session:
            existing = await user_repo.get_by_telegram_id(session, telegram_user_id)
            if existing:
                if existing.plan == "free":
                    await query.edit_message_text(
                        "Ya tienes el plan gratuito activo.\n"
                        "Usa /agregar para añadir tu negocio o /suscribir para mejorar el plan."
                    )
                else:
                    await query.edit_message_text(
                        f"Ya tienes el plan {existing.plan.capitalize()} activo.\n"
                        "Usa /estado para ver tu suscripción."
                    )
                return
            await user_repo.create_free_user(session, telegram_user_id)

        await query.edit_message_text(
            "✅ *Plan gratuito activado.*\n\n"
            "Puedes añadir 1 negocio de Google Maps y recibirás alertas inmediatas de reseñas negativas.\n\n"
            "Usa /agregar para añadir tu negocio.",
            parse_mode="Markdown",
        )
        return

    plan = "pro" if query.data == "subscribe_pro" else "multi"
    price_id = settings.STRIPE_PRO_PRICE_ID if plan == "pro" else settings.STRIPE_MULTI_PRICE_ID

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
            f"Plan *{plan.capitalize()}* seleccionado.\n\n"
            f"Completa el pago aquí:\n{session.url}\n\n"
            "_Tras el pago recibirás un email para activar tu cuenta._",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Error creating Stripe checkout session")
        await query.edit_message_text(
            "Error al crear el enlace de pago. Inténtalo de nuevo en unos minutos."
        )
