import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo

logger = logging.getLogger(__name__)

# Conversation states
ASKING_SEARCH = 0
SELECTING_PLACE = 1
CONFIRMING_OWNERSHIP = 2

PLAN_LIMITS = {"free": 1, "pro": 1, "multi": 3}


@require_subscription(min_plan="free")
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
        "¿Cómo se llama tu negocio?\n"
        "Incluye la ciudad para encontrarlo mejor.\n\n"
        "Ejemplo: *Restaurante El Rincón Madrid*\n\n"
        "Escribe /cancelar para salir.",
        parse_mode="Markdown",
    )
    return ASKING_SEARCH


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Escribe el nombre de tu negocio.")
        return ASKING_SEARCH

    await update.message.reply_text("🔍 Buscando...")

    from app.integrations.google_places import GooglePlacesClient
    results = await GooglePlacesClient().search_by_text(query)

    if not results:
        await update.message.reply_text(
            "No encontré ningún negocio con ese nombre.\n"
            "Prueba con otro nombre o añade la ciudad.\n\n"
            "Escribe /cancelar para salir."
        )
        return ASKING_SEARCH

    context.user_data["search_results"] = results

    rows = []
    for i, place in enumerate(results):
        address_short = place["address"][:50] + ("…" if len(place["address"]) > 50 else "")
        rows.append([
            InlineKeyboardButton(
                f"📍 {place['name']} — {address_short}",
                callback_data=f"place_sel_{i}",
            )
        ])
    rows.append([InlineKeyboardButton("🔍 Buscar de nuevo", callback_data="place_retry")])
    rows.append([InlineKeyboardButton("❌ Cancelar", callback_data="place_cancel")])

    await update.message.reply_text(
        "¿Cuál es tu negocio?",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return SELECTING_PLACE


async def handle_place_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "place_cancel":
        context.user_data.clear()
        await query.edit_message_text("Operación cancelada.")
        return ConversationHandler.END

    if data == "place_retry":
        await query.edit_message_text(
            "¿Cómo se llama tu negocio?\n"
            "Incluye la ciudad para encontrarlo mejor.\n\n"
            "Escribe /cancelar para salir."
        )
        return ASKING_SEARCH

    if data.startswith("place_sel_"):
        try:
            index = int(data[len("place_sel_"):])
        except ValueError:
            await query.edit_message_text("Error inesperado. Usa /agregar para intentarlo de nuevo.")
            return ConversationHandler.END

        results = context.user_data.get("search_results", [])
        if index >= len(results):
            await query.edit_message_text("Error inesperado. Usa /agregar para intentarlo de nuevo.")
            return ConversationHandler.END

        place = results[index]
        context.user_data["selected_place"] = place

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirmar — soy el propietario", callback_data="owner_confirm")],
            [InlineKeyboardButton("🔍 Buscar de nuevo", callback_data="owner_retry")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="owner_cancel")],
        ])

        await query.edit_message_text(
            f"Vas a añadir:\n\n"
            f"📍 *{place['name']}*\n"
            f"📌 {place['address']}\n\n"
            f"Al confirmar, declaras que eres el propietario o representante "
            f"autorizado de este negocio y aceptas nuestros Términos de Servicio.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return CONFIRMING_OWNERSHIP

    return SELECTING_PLACE


async def handle_ownership_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "owner_cancel":
        context.user_data.clear()
        await query.edit_message_text("Operación cancelada.")
        return ConversationHandler.END

    if data == "owner_retry":
        await query.edit_message_text(
            "¿Cómo se llama tu negocio?\n"
            "Incluye la ciudad para encontrarlo mejor.\n\n"
            "Escribe /cancelar para salir."
        )
        return ASKING_SEARCH

    if data == "owner_confirm":
        place = context.user_data.get("selected_place")
        user_id = context.user_data.get("agregar_user_id")

        if not place or not user_id:
            await query.edit_message_text("Error inesperado. Usa /agregar para intentarlo de nuevo.")
            return ConversationHandler.END

        async with AsyncSessionLocal() as session:
            business = await business_repo.create(
                session,
                user_id=user_id,
                name=place["name"],
                google_place_id=place["id"],
                self_declared_owner=True,
            )

        logger.info("Business %d added for user %d via text search", business.id, user_id)
        context.user_data.clear()

        await query.edit_message_text(
            f"✅ *{business.name}* añadido correctamente.\n\n"
            f"📌 {place['address']}\n\n"
            f"Empezaré a monitorizar las reseñas en el próximo ciclo (cada 2 horas).",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    return CONFIRMING_OWNERSHIP


async def cancel_agregar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END
