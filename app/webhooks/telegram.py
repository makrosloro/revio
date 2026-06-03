import logging

from fastapi import APIRouter, Request, Response
from telegram import Update

from app.bot import get_application
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(f"/{settings.TELEGRAM_BOT_TOKEN}/webhook")
async def telegram_webhook(request: Request) -> Response:
    data = await request.json()
    application = get_application()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return Response(status_code=200)
