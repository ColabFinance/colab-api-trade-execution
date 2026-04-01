from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.execution_profile_quote_history_entity import (
    ExecutionProfileQuoteHistoryEntity,
)
from core.repositories.execution_profile_quote_history_repository import (
    ExecutionProfileQuoteHistoryRepository,
)


class ExecutionProfileQuoteHistoryRepositoryMongoDB(
    ExecutionProfileQuoteHistoryRepository
):
    """
    MongoDB repository for execution-profile quote history.
    """

    COLLECTION = "execution_profile_quote_history"

    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db[self.COLLECTION]

    async def ensure_indexes(self) -> None:
        """
        Ensure indexes required for efficient history lookup.
        """
        await self._col.create_index(
            [("execution_account_id", 1), ("symbol", 1), ("closed_at", -1)],
            name="ix_quote_history_profile_closed_at",
        )
        await self._col.create_index(
            [("strategy_id", 1), ("closed_at", -1)],
            name="ix_quote_history_strategy_closed_at",
        )

    def _now(self) -> tuple[int, str]:
        """
        Return current UTC time in milliseconds and ISO string.
        """
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return now_ms, now_iso

    async def insert(
        self,
        entity: ExecutionProfileQuoteHistoryEntity,
    ) -> ExecutionProfileQuoteHistoryEntity:
        """
        Persist one quote-history row.
        """
        now_ms, now_iso = self._now()

        doc = entity.to_mongo()
        doc["created_at"] = now_ms
        doc["created_at_iso"] = now_iso
        doc["updated_at"] = now_ms
        doc["updated_at_iso"] = now_iso

        res = await self._col.insert_one(doc)
        stored = await self._col.find_one({"_id": res.inserted_id})
        return ExecutionProfileQuoteHistoryEntity.from_mongo(stored)

    async def list_paginated(
        self,
        *,
        execution_account_id: str,
        symbol: str,
        limit: int,
        offset: int,
    ) -> List[ExecutionProfileQuoteHistoryEntity]:
        """
        List quote-history rows for one profile with pagination.
        """
        cursor = (
            self._col.find(
                {
                    "execution_account_id": str(execution_account_id).strip(),
                    "symbol": str(symbol).strip().upper(),
                }
            )
            .sort([("closed_at", -1), ("created_at", -1)])
            .skip(int(offset))
            .limit(int(limit))
        )

        docs = await cursor.to_list(length=int(limit))
        return [ExecutionProfileQuoteHistoryEntity.from_mongo(doc) for doc in docs if doc]

    async def count(
        self,
        *,
        execution_account_id: str,
        symbol: str,
    ) -> int:
        """
        Count quote-history rows for one profile.
        """
        return int(
            await self._col.count_documents(
                {
                    "execution_account_id": str(execution_account_id).strip(),
                    "symbol": str(symbol).strip().upper(),
                }
            )
        )