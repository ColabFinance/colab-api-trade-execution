from __future__ import annotations

from typing import List, Optional, Protocol

from core.domain.entities.execution_profile_quote_history_entity import (
    ExecutionProfileQuoteHistoryEntity,
)


class ExecutionProfileQuoteHistoryRepository(Protocol):
    """
    Repository contract for execution-profile quote history.
    """

    async def ensure_indexes(self) -> None:
        """
        Ensure repository indexes exist.
        """
        raise NotImplementedError

    async def insert(
        self,
        entity: ExecutionProfileQuoteHistoryEntity,
    ) -> ExecutionProfileQuoteHistoryEntity:
        """
        Persist one quote-history row.
        """
        raise NotImplementedError

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
        raise NotImplementedError

    async def count(
        self,
        *,
        execution_account_id: str,
        symbol: str,
    ) -> int:
        """
        Count quote-history rows for one profile.
        """
        raise NotImplementedError