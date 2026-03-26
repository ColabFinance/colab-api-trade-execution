from __future__ import annotations

from typing import List, Optional, Protocol

from core.domain.entities.trade_order_entity import TradeOrderEntity


class TradeOrderRepository(Protocol):
    """
    Repository contract for persisted Binance orders.
    """

    async def ensure_indexes(self) -> None:
        """
        Ensure required indexes exist.
        """
        ...

    async def insert(self, entity: TradeOrderEntity) -> TradeOrderEntity:
        """
        Insert an order document.
        """
        ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[TradeOrderEntity]:
        """
        Fetch an order by idempotency key.
        """
        ...

    async def list_by_strategy_id(self, strategy_id: str, limit: int) -> List[TradeOrderEntity]:
        """
        List orders for one strategy.
        """
        ...