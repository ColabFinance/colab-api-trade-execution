from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict

from core.domain.entities.base_entity import MongoEntity


class TradePositionEntity(MongoEntity):
    """
    Canonical trade position entity.

    This document represents the position lifecycle managed by
    api-trade-execution.
    """

    strategy_id: str
    execution_account_id: str
    symbol: str
    position_side: str

    status: str = "OPEN"

    quantity: float
    entry_price: float

    open_order_id: Optional[str] = None
    close_order_id: Optional[str] = None

    signal_open_id: Optional[str] = None
    signal_close_id: Optional[str] = None

    open_reason: Optional[str] = None
    close_reason: Optional[str] = None

    opened_at: int
    opened_at_iso: Optional[str] = None

    closed_at: Optional[int] = None
    closed_at_iso: Optional[str] = None

    exit_price: Optional[float] = None

    model_config = ConfigDict(extra="ignore")