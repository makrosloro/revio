import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import AsyncSessionLocal, engine
from app.webhooks.stripe import router as stripe_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Arrancando NegocioSano...")
    yield
    logger.info("Apagando NegocioSano...")
    await engine.dispose()


app = FastAPI(title="NegocioSano", lifespan=lifespan)

app.include_router(stripe_router, prefix="/webhook")


@app.get("/health")
async def health() -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}
