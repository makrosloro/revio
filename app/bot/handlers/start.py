from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.activar import run_activar


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bienvenida. Si llega con token (deep link), activa la cuenta directamente."""
    if context.args:
        await run_activar(update, context, token=context.args[0])
        return

    await update.message.reply_text(
        "Bienvenido a NegocioSano — reputación online para tu negocio.\n"
        "Monitorizo tus reseñas de Google, te aviso al instante de las negativas "
        "y te preparo borradores de respuesta con IA.\n\n"
        "Comandos:\n"
        "/suscribir — elige tu plan (Pro 29€ / Multi 59€)\n"
        "/activar TOKEN — activa tu cuenta tras el pago\n"
        "/estado — ver tu plan y suscripción\n"
        "/agregar — añadir un negocio a monitorizar\n"
        "/config — ver tus negocios activos\n"
        "/pausa — pausar alertas de un negocio\n"
        "/reanudar — reanudar alertas"
    )
