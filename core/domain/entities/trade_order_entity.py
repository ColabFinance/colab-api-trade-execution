from __future__ import annotations

from typing import Any, Optional

from pydantic import ConfigDict

from core.domain.entities.base_entity import MongoEntity


class TradeOrderEntity(MongoEntity):
    """
    Canonical trade order entity.

    Every open or close action sent to Binance is persisted as an order document.
    """

    action: str
    idempotency_key: str

    strategy_id: str
    execution_account_id: str
    symbol: str
    position_side: str
    side: str

    quantity: float
    signal_id: Optional[str] = None
    signal_ts: Optional[int] = None

    binance_order_id: Optional[str] = None
    status: str = "SENT"

    raw_response: Optional[dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")