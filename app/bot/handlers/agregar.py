import logging
import re

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo

logger = logging.getLogger(__name__)

ASKING_NAME = 0
ASKING_LINK = 1

PLAN_LIMITS = {"free": 0, "pro": 1, "multi": 3}


def _extract_place_id(text: str) -> str | None:
    text = text.strip()
    if re.match(r"^ChIJ[A-Za-z0-9_-]+$", text):
        return text
    match = re.search(r"place_id=([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"!1s(ChIJ[A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    return None


@require_subscription(min_plan="pro")
async def agregar(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> int:
    async with AsyncSessionLocal() as session:
        count = await business_repo.count_by_user(session, user.id)

    limit = PLAN_LIMITS.get(user.plan, 0)
    if count >= limit:
        await update.message.reply_text(
            f"Has alcanzado el límite de {limit} negocio(s) para el plan {user.plan.capitalize()}.\n"
            "Usa /suscribir para mejorar tu plan."
        )
        return ConversationHandler.END

    context.user_data["agregar_user_id"] = user.id
    await update.message.reply_text(
        "¿Cómo se llama el negocio? (ej: Restaurante El Rincón)\n\n"
        "Escribe /cancelar para salir."
    )
    return ASKING_NAME


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()[:255]
    if not name:
        await update.message.reply_text("El nombre no puede estar vacío. Inténtalo de nuevo.")
        return ASKING_NAME

    context.user_data["agregar_name"] = name
    await update.message.reply_text(
        f"Nombre guardado: {name}\n\n"
        "Ahora pega el Place ID de Google Maps o la URL de Google Maps.\n"
        "Puedes encontrar el Place ID en Google Places API o en la URL de Google Maps.\n\n"
        "Escribe /cancelar para salir."
    )
    return ASKING_LINK


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()[:500]
    place_id = _extract_place_id(text)

    if not place_id:
        await update.message.reply_text(
            "No pude extraer el Place ID de ese texto.\n"
            "Pega directamente el Place ID (empieza por ChIJ...) o la URL completa de Google Maps.\n"
            "Escribe /cancelar para salir."
        )
        return ASKING_LINK

    user_id = context.user_data.get("agregar_user_id")
    name = context.user_data.get("agregar_name")

    async with AsyncSessionLocal() as session:
        business = await business_repo.create(session, user_id, name, place_id)

    await update.message.reply_text(
        f"Negocio añadido correctamente.\n"
        f"Nombre: {business.name}\n"
        f"Place ID: {business.google_place_id}\n\n"
        "Empezaré a monitorizar las reseñas en el próximo ciclo de polling."
    )
    logger.info("Business %s added for user %s", business.id, user_id)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_agregar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END
