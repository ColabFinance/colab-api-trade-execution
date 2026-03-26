from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.trade_order_entity import TradeOrderEntity
from core.repositories.trade_order_repository import TradeOrderRepository


class TradeOrderRepositoryMongoDB(TradeOrderRepository):
    """
    MongoDB repository for persisted Binance order documents.
    """

    COLLECTION = "trade_orders"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the repository with a MongoDB database handle.
        """
        self._col = db[self.COLLECTION]

    async def ensure_indexes(self) -> None:
        """
        Ensure indexes required for idempotent execution and history reads.
        """
        await self._col.create_index(
            [("idempotency_key", 1)],
            unique=True,
            name="ux_trade_order_idempotency_key",
        )
        await self._col.create_index(
            [("strategy_id", 1), ("created_at", -1)],
            name="ix_trade_order_strategy_created_at",
        )
        await self._col.create_index(
            [("execution_account_id", 1), ("symbol", 1), ("created_at", -1)],
            name="ix_trade_order_account_symbol_created_at",
        )

    def _now(self) -> tuple[int, str]:
        """
        Return current UTC time in milliseconds and ISO string.
        """
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return now_ms, now_iso

    async def insert(self, entity: TradeOrderEntity) -> TradeOrderEntity:
        """
        Insert one order document.
        """
        now_ms, now_iso = self._now()

        payload = entity.to_mongo()
        payload["created_at"] = now_ms
        payload["created_at_iso"] = now_iso

        res = await self._col.insert_one(payload)
        stored = await self._col.find_one({"_id": res.inserted_id})
        return TradeOrderEntity.from_mongo(stored)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[TradeOrderEntity]:
        """
        Fetch an order by idempotency key.
        """
        doc = await self._col.find_one({"idempotency_key": str(idempotency_key)})
        return TradeOrderEntity.from_mongo(doc) if doc else None

    async def list_by_strategy_id(self, strategy_id: str, limit: int) -> List[TradeOrderEntity]:
        """
        List order history for one strategy.
        """
        cursor = (
            self._col.find({"strategy_id": str(strategy_id)})
            .sort([("created_at", -1)])
            .limit(int(limit))
        )
        docs = await cursor.to_list(length=int(limit))
        return [TradeOrderEntity.from_mongo(doc) for doc in docs if doc]