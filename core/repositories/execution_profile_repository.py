from __future__ import annotations

from typing import List, Optional, Protocol

from core.domain.entities.execution_profile_entity import ExecutionProfileEntity


class ExecutionProfileRepository(Protocol):
    """
    Repository contract for execution profiles.
    """

    async def ensure_indexes(self) -> None:
        """
        Ensure required indexes exist.
        """
        raise NotImplementedError

    async def upsert(self, entity: ExecutionProfileEntity) -> ExecutionProfileEntity:
        """
        Upsert an execution profile.
        """
        raise NotImplementedError

    async def get_by_account_symbol(
        self,
        execution_account_id: str,
        symbol: str,
    ) -> Optional[ExecutionProfileEntity]:
        """
        Fetch one execution profile by account and symbol.
        """
        raise NotImplementedError

    async def list(
        self,
        execution_account_id: Optional[str] = None,
    ) -> List[ExecutionProfileEntity]:
        """
        List execution profiles, optionally filtered by account.
        """
        raise NotImplementedError