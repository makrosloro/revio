import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from telegram import Update

from app.bot import create_application
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.scheduler.tasks import create_scheduler, setup_jobs
from app.webhooks.stripe import router as stripe_router
from app.webhooks.telegram import router as telegram_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Arrancando NegocioSano...")

    bot_app = create_application(settings.TELEGRAM_BOT_TOKEN)
    await bot_app.initialize()
    webhook_url = f"{settings.WEBHOOK_URL}/{settings.TELEGRAM_BOT_TOKEN}/webhook"
    await bot_app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    await bot_app.start()
    logger.info("Bot webhook configurado en %s", webhook_url)

    scheduler = create_scheduler()
    setup_jobs(scheduler)
    scheduler.start()
    logger.info("Scheduler iniciado")

    yield

    logger.info("Apagando NegocioSano...")
    scheduler.shutdown(wait=False)
    await bot_app.stop()
    await bot_app.shutdown()
    await engine.dispose()


app = FastAPI(title="NegocioSano", lifespan=lifespan)

app.include_router(stripe_router, prefix="/webhook")
app.include_router(telegram_router)


@app.get("/health")
async def health() -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


@app.get("/payment/success")
async def payment_success() -> dict:
    return {"status": "ok", "message": "Pago completado. Revisa tu email para activar tu cuenta en Telegram."}
