from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.execution_profile_entity import ExecutionProfileEntity
from core.repositories.execution_profile_repository import ExecutionProfileRepository


class ExecutionProfileRepositoryMongoDB(ExecutionProfileRepository):
    """
    MongoDB repository for execution profiles.
    """

    COLLECTION = "execution_profiles"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the repository with a MongoDB database handle.
        """
        self._col = db[self.COLLECTION]

    async def ensure_indexes(self) -> None:
        """
        Ensure indexes required for execution profile lookup.
        """
        await self._col.create_index(
            [("execution_account_id", 1), ("symbol", 1)],
            unique=True,
            name="ux_execution_profile_account_symbol",
        )
        await self._col.create_index(
            [("execution_account_id", 1), ("is_enabled", 1)],
            name="ix_execution_profile_account_enabled",
        )

    def _now(self) -> tuple[int, str]:
        """
        Return current UTC time in milliseconds and ISO string.
        """
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return now_ms, now_iso

    async def upsert(self, entity: ExecutionProfileEntity) -> ExecutionProfileEntity:
        """
        Upsert an execution profile document.
        """
        now_ms, now_iso = self._now()

        payload = entity.to_mongo()
        payload["updated_at"] = now_ms
        payload["updated_at_iso"] = now_iso

        await self._col.update_one(
            {
                "execution_account_id": entity.execution_account_id,
                "symbol": entity.symbol,
            },
            {
                "$set": payload,
                "$setOnInsert": {
                    "created_at": now_ms,
                    "created_at_iso": now_iso,
                },
            },
            upsert=True,
        )

        stored = await self._col.find_one(
            {
                "execution_account_id": entity.execution_account_id,
                "symbol": entity.symbol,
            }
        )
        return ExecutionProfileEntity.from_mongo(stored)

    async def get_by_account_symbol(
        self,
        execution_account_id: str,
        symbol: str,
    ) -> Optional[ExecutionProfileEntity]:
        """
        Fetch one execution profile by account and symbol.
        """
        doc = await self._col.find_one(
            {
                "execution_account_id": str(execution_account_id).strip(),
                "symbol": str(symbol).strip().upper(),
            }
        )
        return ExecutionProfileEntity.from_mongo(doc) if doc else None

    async def list(
        self,
        execution_account_id: Optional[str] = None,
    ) -> List[ExecutionProfileEntity]:
        """
        List execution profiles, optionally filtered by account.
        """
        query: dict = {}
        if execution_account_id:
            query["execution_account_id"] = str(execution_account_id).strip()

        cursor = self._col.find(query).sort([("execution_account_id", 1), ("symbol", 1)])
        docs = await cursor.to_list(length=None)
        return [ExecutionProfileEntity.from_mongo(doc) for doc in docs if doc]