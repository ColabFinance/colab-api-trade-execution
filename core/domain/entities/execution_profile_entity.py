from __future__ import annotations

from pydantic import ConfigDict

from core.domain.entities.base_entity import MongoEntity


class ExecutionProfileEntity(MongoEntity):
    """
    Execution profile used by api-trade-execution.

    This profile defines how a symbol should be executed for a given
    execution account, including the quote notional size and leverage.
    """

    execution_account_id: str
    symbol: str
    is_enabled: bool = True
    quote_size_usd: float
    leverage: int

    model_config = ConfigDict(extra="ignore")