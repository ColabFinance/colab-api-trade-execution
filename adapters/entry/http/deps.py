from __future__ import annotations

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorDatabase


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """
    Return the MongoDB database handle stored in app.state.
    """
    return request.app.state.mongo_db