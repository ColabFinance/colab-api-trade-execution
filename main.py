from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.entry.http.execution_profile_router import router as execution_profile_router
from adapters.entry.http.trade_execution_router import router as trade_execution_router
from adapters.external.binance.binance_futures_client import BinanceFuturesClient
from adapters.external.database.mongodb_client import get_mongo_client
from config.settings import settings


def _setup_logging() -> None:
    """
    Configure service logging.
    """
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Service startup and shutdown lifecycle.
    """
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting api-trade-execution...")

    mongo_client = get_mongo_client()
    db = mongo_client[settings.MONGODB_DB_NAME]

    binance_client = BinanceFuturesClient()

    app.state.mongo_client = mongo_client
    app.state.mongo_db = db
    app.state.binance_futures_client = binance_client

    try:
        await db.command("ping")
        await binance_client.ping()
        logger.info("MongoDB and Binance connectivity checks passed.")
    except Exception:
        logger.exception("Startup connectivity check failed.")
        raise

    try:
        yield
    finally:
        logger.info("Shutting down api-trade-execution...")
        mongo_client.close()


app = FastAPI(title="api-trade-execution", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(execution_profile_router, prefix="/api")
app.include_router(trade_execution_router, prefix="/api")


@app.get("/healthz")
async def healthz():
    """
    Basic health endpoint.
    """
    return {"status": "ok"}