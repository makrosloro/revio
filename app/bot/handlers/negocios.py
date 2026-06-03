import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.middleware import require_subscription
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories import business_repo

logger = logging.getLogger(__name__)

_TONE_LABELS = {"cercano": "Cercano", "profesional": "Profesional", "formal": "Formal"}
_PLAN_LIMITS = {"free": 1, "pro": 1, "multi": 3}


@require_subscription(min_plan="free")
async def negocios(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User = None) -> None:
    async with AsyncSessionLocal() as session:
        rows = await business_repo.get_with_review_counts(session, user.id)

    limit = _PLAN_LIMITS.get(user.plan, 1)

    if not rows:
        await update.message.reply_text(
            "Aún no tienes negocios añadidos.\n\n"
            f"Tu plan {user.plan.capitalize()} permite hasta {limit} negocio(s).\n"
            "Usa /agregar para añadir el primero."
        )
        return

    lines = [f"📍 *Tus negocios* ({len(rows)}/{limit})\n"]
    for i, (b, review_count) in enumerate(rows, 1):
        status = "⏸ Pausado" if b.is_paused else "▶ Activo"
        tone = _TONE_LABELS.get(b.tone or "cercano", b.tone or "cercano")
        lines.append(
            f"*{i}. {b.name}*\n"
            f"   {status} · 🗣 {tone} · {review_count} reseña(s)"
        )

    footer = ["\nUsa /config para cambiar el tono · /pausa para pausar alertas"]
    if len(rows) < limit:
        footer.insert(0, "\nPuedes añadir otro negocio con /agregar")
    else:
        footer.insert(0, "\nHas alcanzado el límite de tu plan. /suscribir para ampliar")

    await update.message.reply_text(
        "\n".join(lines + footer),
        parse_mode="Markdown",
    )
