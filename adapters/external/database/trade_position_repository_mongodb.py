from __future__ import annotations

from typing import List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.trade_position_entity import TradePositionEntity
from core.repositories.trade_position_repository import TradePositionRepository


class TradePositionRepositoryMongoDB(TradePositionRepository):
    """
    MongoDB repository for trade positions.
    """

    COLLECTION = "trade_positions"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the repository with a MongoDB database handle.
        """
        self._col = db[self.COLLECTION]

    async def ensure_indexes(self) -> None:
        """
        Ensure indexes required for active position lookup.
        """
        await self._col.create_index(
            [("strategy_id", 1), ("execution_account_id", 1), ("symbol", 1), ("status", 1)],
            name="ix_trade_position_strategy_account_symbol_status",
        )
        await self._col.create_index(
            [("execution_account_id", 1), ("status", 1)],
            name="ix_trade_position_account_status",
        )

    async def upsert_open(self, entity: TradePositionEntity) -> TradePositionEntity:
        """
        Upsert an open position document by strategy/account/symbol/status.
        """
        await self._col.update_one(
            {
                "strategy_id": entity.strategy_id,
                "execution_account_id": entity.execution_account_id,
                "symbol": entity.symbol,
                "status": "OPEN",
            },
            {"$set": entity.to_mongo()},
            upsert=True,
        )

        stored = await self._col.find_one(
            {
                "strategy_id": entity.strategy_id,
                "execution_account_id": entity.execution_account_id,
                "symbol": entity.symbol,
                "status": "OPEN",
            }
        )
        return TradePositionEntity.from_mongo(stored)

    async def get_active_by_strategy(
        self,
        strategy_id: str,
        execution_account_id: str,
        symbol: str,
    ) -> Optional[TradePositionEntity]:
        """
        Fetch the currently active position for a strategy/account/symbol.
        """
        doc = await self._col.find_one(
            {
                "strategy_id": str(strategy_id),
                "execution_account_id": str(execution_account_id).strip(),
                "symbol": str(symbol).strip().upper(),
                "status": "OPEN",
            }
        )
        return TradePositionEntity.from_mongo(doc) if doc else None

    async def mark_closed(
        self,
        *,
        position_id: str,
        close_order_id: str,
        close_reason: str,
        signal_close_id: Optional[str],
        closed_at: int,
        closed_at_iso: str,
        exit_price: float,
    ) -> Optional[TradePositionEntity]:
        """
        Mark an open position as closed and return the updated document.
        """
        await self._col.update_one(
            {"_id": ObjectId(position_id)},
            {
                "$set": {
                    "status": "CLOSED",
                    "close_order_id": str(close_order_id),
                    "close_reason": str(close_reason),
                    "signal_close_id": signal_close_id,
                    "closed_at": int(closed_at),
                    "closed_at_iso": str(closed_at_iso),
                    "exit_price": float(exit_price),
                }
            },
        )
        doc = await self._col.find_one({"_id": ObjectId(position_id)})
        return TradePositionEntity.from_mongo(doc) if doc else None

    async def list_active(
        self,
        execution_account_id: Optional[str] = None,
    ) -> List[TradePositionEntity]:
        """
        List active positions, optionally filtered by execution account.
        """
        query: dict = {"status": "OPEN"}
        if execution_account_id:
            query["execution_account_id"] = str(execution_account_id).strip()

        cursor = self._col.find(query).sort([("opened_at", -1)])
        docs = await cursor.to_list(length=None)
        return [TradePositionEntity.from_mongo(doc) for doc in docs if doc]