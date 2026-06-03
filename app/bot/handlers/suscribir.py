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


_PLAN_RANK = {"free": 0, "pro": 1, "multi": 2}

_PLAN_BUTTONS = {
    "free": ("🆓 Plan Gratuito — 0€", "subscribe_free"),
    "pro": ("💼 Plan Pro — 29€/mes", "subscribe_pro"),
    "multi": ("🏢 Plan Multi — 59€/mes", "subscribe_multi"),
}

_PLAN_DESCS = {
    "free": "🆓 *Gratuito* — 1 negocio · Google Maps · Alertas sin borrador",
    "pro": "💼 *Pro — 29€/mes* — 1 negocio · Alertas con borrador IA · Resumen diario",
    "multi": "🏢 *Multi — 59€/mes* — 3 negocios · Todo lo de Pro · Publicación en Google",
}


def _plans_above(current_plan: str | None) -> list[str]:
    """Return plan keys strictly above the user's current plan."""
    current_rank = _PLAN_RANK.get(current_plan, -1)
    return [p for p, rank in _PLAN_RANK.items() if rank > current_rank]


def _plans_keyboard(plans: list[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(_PLAN_BUTTONS[p][0], callback_data=_PLAN_BUTTONS[p][1])] for p in plans]
    )


async def suscribir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        user = await user_repo.get_by_telegram_id(session, telegram_user_id)

    current_plan = user.plan if user else None
    available = _plans_above(current_plan)

    if not available:
        await update.message.reply_text(
            "🏢 Ya tienes el plan *Multi*, el más completo. ¡Gracias!\n\n"
            "Usa /estado para ver tu suscripción o /negocios para ver tus locales.",
            parse_mode="Markdown",
        )
        return

    if current_plan:
        intro = f"Tu plan actual es *{current_plan.capitalize()}*. Puedes mejorar a:\n\n"
    else:
        intro = "Elige tu plan:\n\n"

    body = "\n\n".join(_PLAN_DESCS[p] for p in available)
    await update.message.reply_text(
        intro + body,
        parse_mode="Markdown",
        reply_markup=_plans_keyboard(available),
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

    # Guard: never allow buying a plan equal to or below the current one
    async with AsyncSessionLocal() as session:
        existing = await user_repo.get_by_telegram_id(session, telegram_user_id)
    if existing and _PLAN_RANK.get(plan, 0) <= _PLAN_RANK.get(existing.plan, -1):
        await query.edit_message_text(
            f"Ya tienes el plan {existing.plan.capitalize()}. "
            "Usa /estado para ver tu suscripción."
        )
        return

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
        pay_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Completar pago", url=session.url)]
        ])
        await query.edit_message_text(
            f"Plan {plan.capitalize()} seleccionado.\n\n"
            "Pulsa el botón para completar el pago de forma segura con Stripe.\n\n"
            "Tras el pago recibirás un email para activar tu cuenta.",
            reply_markup=pay_keyboard,
        )
    except Exception:
        logger.exception("Error creating Stripe checkout session")
        await query.edit_message_text(
            "Error al crear el enlace de pago. Inténtalo de nuevo en unos minutos."
        )
