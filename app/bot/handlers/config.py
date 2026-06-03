from telegram import Update
from telegram.ext import ContextTypes

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo


@require_subscription(min_plan="pro")
async def config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> None:
    async with AsyncSessionLocal() as session:
        businesses = await business_repo.get_all_by_user(session, user.id)

    if not businesses:
        await update.message.reply_text(
            "Aún no tienes negocios añadidos.\n"
            "Usa /agregar para añadir tu primer negocio."
        )
        return

    lines = ["Tus negocios monitorizados:\n"]
    for i, b in enumerate(businesses, 1):
        status = "⏸ Pausado" if b.is_paused else "▶ Activo"
        lines.append(f"{i}. {b.name} — {status}")

    lines.append("\nUsa /agregar para añadir más negocios.")
    await update.message.reply_text("\n".join(lines))
