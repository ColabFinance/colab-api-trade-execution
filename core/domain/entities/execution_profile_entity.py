from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict

from core.domain.entities.base_entity import MongoEntity


class ExecutionProfileEntity(MongoEntity):
    """
    Execution profile used by api-trade-execution.

    This profile defines how a symbol should be executed for a given
    execution account, including the quote notional size and leverage.

    `quote_size_usd` is the current active quote used for the next order.
    `initial_quote_size_usd` preserves the original configured base value.
    """

    execution_account_id: str
    symbol: str
    is_enabled: bool = True

    quote_size_usd: float
    initial_quote_size_usd: Optional[float] = None

    leverage: int

    model_config = ConfigDict(extra="ignore")