import asyncio
import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import user_repo
from app.services.email_service import send_activation_email

logger = logging.getLogger(__name__)
router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY


async def _notify_user(telegram_user_id: int, text: str) -> None:
    if not telegram_user_id:
        return
    try:
        from telegram import Bot
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=telegram_user_id, text=text)
    except Exception:
        logger.warning("Could not notify telegram_user_id %s", telegram_user_id)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> dict:
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    asyncio.create_task(_handle_event(event))
    return {"received": True}


async def _handle_event(event: dict) -> None:
    event_type = event["type"]
    data = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            await _on_checkout_completed(data)
        elif event_type == "customer.subscription.deleted":
            await _on_subscription_deleted(data)
        elif event_type == "customer.subscription.updated":
            await _on_subscription_updated(data)
        elif event_type == "invoice.payment_failed":
            await _on_payment_failed(data)
    except Exception:
        logger.exception("Error handling Stripe event %s", event_type)


async def _on_checkout_completed(session: dict) -> None:
    email = (session.get("customer_details") or {}).get("email") or session.get("customer_email")
    stripe_customer_id = session.get("customer")
    stripe_sub_id = session.get("subscription")
    metadata = session.get("metadata") or {}
    plan = metadata.get("plan", "pro")

    if not email or not stripe_sub_id:
        logger.warning("checkout.session.completed missing email or sub_id")
        return

    async with AsyncSessionLocal() as db:
        existing = await user_repo.get_by_email(db, email)
        if existing:
            await user_repo.update_subscription(db, existing.stripe_subscription_id or stripe_sub_id, "active", plan)
            user = existing
        else:
            user = await user_repo.create_from_stripe(db, email, stripe_customer_id, stripe_sub_id, plan)

    await send_activation_email(email, user.activation_token)
    logger.info("New subscription: email=%s plan=%s", email, plan)


async def _on_subscription_deleted(sub: dict) -> None:
    stripe_sub_id = sub["id"]
    async with AsyncSessionLocal() as db:
        user = await _get_user_by_sub(db, stripe_sub_id)
        await user_repo.update_subscription(db, stripe_sub_id, "cancelled")

    if user and user.telegram_user_id:
        await _notify_user(
            user.telegram_user_id,
            "Tu suscripción de NegocioSano ha sido cancelada. Usa /suscribir para renovarla.",
        )


async def _on_subscription_updated(sub: dict) -> None:
    stripe_sub_id = sub["id"]
    sub_status = sub.get("status", "active")
    items = sub.get("items", {}).get("data", [])
    plan = None
    if items:
        price_id = items[0].get("price", {}).get("id")
        if price_id == settings.STRIPE_PRO_PRICE_ID:
            plan = "pro"
        elif price_id == settings.STRIPE_MULTI_PRICE_ID:
            plan = "multi"

    async with AsyncSessionLocal() as db:
        await user_repo.update_subscription(db, stripe_sub_id, sub_status, plan)


async def _on_payment_failed(invoice: dict) -> None:
    stripe_customer_id = invoice.get("customer")
    stripe_sub_id = invoice.get("subscription")

    async with AsyncSessionLocal() as db:
        user = await user_repo.get_by_stripe_customer(db, stripe_customer_id)
        if stripe_sub_id:
            await user_repo.update_subscription(db, stripe_sub_id, "past_due")

    if user and user.telegram_user_id:
        await _notify_user(
            user.telegram_user_id,
            "El pago de tu suscripción de NegocioSano ha fallado. "
            "Actualiza tu método de pago para no perder el servicio.",
        )


async def _get_user_by_sub(db, stripe_sub_id: str):
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(
        select(User).where(User.stripe_subscription_id == stripe_sub_id)
    )
    return result.scalar_one_or_none()
