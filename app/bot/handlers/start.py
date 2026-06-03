from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.handlers.activar import run_activar
from app.database import AsyncSessionLocal
from app.repositories import user_repo


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message. Deep-link activation if token passed."""
    if context.args:
        await run_activar(update, context, token=context.args[0])
        return

    telegram_user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        user = await user_repo.get_by_telegram_id(session, telegram_user_id)

    if user:
        plan_label = {"free": "Free", "pro": "Pro", "multi": "Multi"}.get(user.plan, user.plan)
        await update.message.reply_text(
            f"Bienvenido de nuevo a NegocioSano. 👋\n"
            f"Plan activo: *{plan_label}*\n\n"
            f"Comandos disponibles:\n"
            f"/agregar — añadir un negocio\n"
            f"/negocios — ver tus negocios añadidos\n"
            f"/resenas — ver reseñas recientes\n"
            f"/responder — generar borrador de respuesta\n"
            f"/config — configurar tono de respuesta\n"
            f"/estado — ver tu suscripción\n"
            f"/suscribir — mejorar de plan",
            parse_mode="Markdown",
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 Empezar gratis", callback_data="signup_free")],
        [InlineKeyboardButton("💼 Ver planes Pro y Multi", callback_data="signup_show_plans")],
    ])
    await update.message.reply_text(
        "*Bienvenido a NegocioSano* 🌿\n\n"
        "Monitorizo tus reseñas de Google, te aviso al instante de las negativas "
        "y genero borradores de respuesta con IA.\n\n"
        "¿Cómo quieres empezar?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def handle_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    telegram_user_id = update.effective_user.id

    if query.data == "signup_free":
        async with AsyncSessionLocal() as session:
            existing = await user_repo.get_by_telegram_id(session, telegram_user_id)
            if existing:
                await query.edit_message_text(
                    "Ya tienes una cuenta activa. Usa /agregar para añadir tu negocio."
                )
                return
            await user_repo.create_free_user(session, telegram_user_id)

        await query.edit_message_text(
            "✅ *Cuenta gratuita activada.*\n\n"
            "Puedes monitorizar 1 negocio en Google Maps y recibirás alertas "
            "inmediatas de reseñas negativas.\n\n"
            "Usa /agregar para añadir tu negocio ahora.",
            parse_mode="Markdown",
        )

    elif query.data == "signup_show_plans":
        from app.bot.keyboards import subscription_keyboard
        await query.edit_message_text(
            "Elige el plan que mejor se adapte a tu negocio:\n\n"
            "💼 *Pro — 29€/mes*\n"
            "1 negocio · Alertas inmediatas · Borradores IA · Resumen diario\n\n"
            "🏢 *Multi — 59€/mes*\n"
            "Hasta 3 negocios · Todo lo de Pro · Publicación directa en Google\n\n"
            "_Tras el pago recibirás un email para activar la cuenta en Telegram._",
            parse_mode="Markdown",
            reply_markup=subscription_keyboard(),
        )
