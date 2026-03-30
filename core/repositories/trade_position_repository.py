from __future__ import annotations

from typing import List, Optional, Protocol

from core.domain.entities.trade_position_entity import TradePositionEntity


class TradePositionRepository(Protocol):
    """
    Repository contract for trade positions.
    """

    async def ensure_indexes(self) -> None:
        """
        Ensure required indexes exist.
        """
        raise NotImplementedError

    async def upsert_open(self, entity: TradePositionEntity) -> TradePositionEntity:
        """
        Upsert an open position document.
        """
        raise NotImplementedError

    async def get_active_by_strategy(
        self,
        strategy_id: str,
        execution_account_id: str,
        symbol: str,
    ) -> Optional[TradePositionEntity]:
        """
        Fetch the active position for one strategy/account/symbol combination.
        """
        raise NotImplementedError

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
        Mark a position as closed.
        """
        raise NotImplementedError

    async def list_active(
        self,
        execution_account_id: Optional[str] = None,
    ) -> List[TradePositionEntity]:
        """
        List active positions.
        """
        raise NotImplementedError

    async def list_paginated(
        self,
        *,
        execution_account_id: Optional[str] = None,
        status_scope: str = "OPEN",
        limit: int = 10,
        offset: int = 0,
    ) -> List[TradePositionEntity]:
        """
        List positions with pagination and status scope support.
        """
        raise NotImplementedError

    async def count(
        self,
        *,
        execution_account_id: Optional[str] = None,
        status_scope: str = "OPEN",
    ) -> int:
        """
        Count positions for pagination and status scope support.
        """
        raise NotImplementedError