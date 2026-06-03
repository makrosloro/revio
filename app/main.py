import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from telegram import Update

from app.admin.router import router as admin_router
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
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


@app.get("/payment/success")
async def payment_success():
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pago completado — NegocioSano</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0fdf4;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{background:#fff;border-radius:16px;padding:48px 40px;max-width:480px;width:90%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08)}
  .icon{font-size:56px;margin-bottom:16px}
  h1{color:#16a34a;font-size:24px;margin:0 0 12px}
  p{color:#4b5563;line-height:1.6;margin:0 0 16px}
  .steps{background:#f0fdf4;border-radius:10px;padding:20px;text-align:left;margin:24px 0}
  .step{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start}
  .step:last-child{margin-bottom:0}
  .num{background:#16a34a;color:#fff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;margin-top:2px}
  .step p{margin:0;color:#374151;font-size:14px}
  .badge{background:#16a34a;color:#fff;border-radius:20px;padding:4px 12px;font-size:12px;font-weight:600;display:inline-block;margin-bottom:20px}
</style>
</head>
<body>
<div class="card">
  <div class="icon">✅</div>
  <span class="badge">Pago completado</span>
  <h1>¡Bienvenido a NegocioSano!</h1>
  <p>Tu suscripción está activa. Revisa tu email — te hemos enviado un enlace para activar tu cuenta en Telegram.</p>
  <div class="steps">
    <div class="step"><div class="num">1</div><p><strong>Revisa tu email</strong> y busca el mensaje de NegocioSano con tu token de activación.</p></div>
    <div class="step"><div class="num">2</div><p><strong>Abre Telegram</strong> y envía <code>/activar TOKEN</code> al bot, o haz clic en el enlace del email.</p></div>
    <div class="step"><div class="num">3</div><p><strong>Añade tu negocio</strong> con <code>/agregar</code> y empieza a recibir alertas de reseñas.</p></div>
  </div>
  <p style="font-size:13px;color:#6b7280">¿No recibes el email? Revisa la carpeta de spam o contacta con soporte.</p>
</div>
</body></html>"""
    return HTMLResponse(content=html)


@app.get("/payment/cancel")
async def payment_cancel():
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pago cancelado — NegocioSano</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#fff7ed;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{background:#fff;border-radius:16px;padding:48px 40px;max-width:480px;width:90%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08)}
  .icon{font-size:56px;margin-bottom:16px}
  h1{color:#ea580c;font-size:24px;margin:0 0 12px}
  p{color:#4b5563;line-height:1.6;margin:0 0 16px}
  .btn{display:inline-block;background:#ea580c;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;margin-top:8px}
  .btn:hover{background:#c2410c}
  .note{font-size:13px;color:#6b7280;margin-top:20px}
</style>
</head>
<body>
<div class="card">
  <div class="icon">↩️</div>
  <h1>Pago cancelado</h1>
  <p>No se ha realizado ningún cargo. Puedes intentarlo de nuevo cuando quieras.</p>
  <p>Si tuviste algún problema durante el pago o tienes dudas sobre los planes, estamos aquí para ayudarte.</p>
  <p class="note">¿Preguntas? Escríbenos a <strong>hola@negociosano.com</strong></p>
</div>
</body></html>"""
    return HTMLResponse(content=html)
