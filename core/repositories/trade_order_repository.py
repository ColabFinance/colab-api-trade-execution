from __future__ import annotations

from typing import List, Optional, Protocol

from core.domain.entities.trade_order_entity import TradeOrderEntity


class TradeOrderRepository(Protocol):
    """
    Repository contract for persisted Binance orders.
    """

    async def ensure_indexes(self) -> None:
        raise NotImplementedError

    async def insert(self, entity: TradeOrderEntity) -> TradeOrderEntity:
        raise NotImplementedError

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[TradeOrderEntity]:
        raise NotImplementedError

    async def list_by_strategy_id(self, strategy_id: str, limit: int) -> List[TradeOrderEntity]:
        raise NotImplementedError

    async def list_paginated(
        self,
        *,
        strategy_id: Optional[str] = None,
        execution_account_id: Optional[str] = None,
        lifecycle_scope: str = "OPEN",
        limit: int = 10,
        offset: int = 0,
    ) -> List[TradeOrderEntity]:
        raise NotImplementedError

    async def count(
        self,
        *,
        strategy_id: Optional[str] = None,
        execution_account_id: Optional[str] = None,
        lifecycle_scope: str = "OPEN",
    ) -> int:
        raise NotImplementedError