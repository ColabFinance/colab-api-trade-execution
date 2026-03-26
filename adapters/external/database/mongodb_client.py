from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from config.settings import settings


def get_mongo_client() -> AsyncIOMotorClient:
    """
    Build a configured shared MongoDB client.
    """
    return AsyncIOMotorClient(
        settings.MONGODB_URI,
        uuidRepresentation="standard",
        maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGODB_SOCKET_TIMEOUT_MS,
    )