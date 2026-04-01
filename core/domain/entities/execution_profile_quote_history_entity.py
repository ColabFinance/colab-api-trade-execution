from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict

from core.domain.entities.base_entity import MongoEntity


class ExecutionProfileQuoteHistoryEntity(MongoEntity):
    """
    Historical record of automatic quote-size changes for one execution profile.

    One document is written every time a closed trade updates the profile quote.
    """

    execution_account_id: str
    symbol: str
    strategy_id: Optional[str] = None
    position_id: Optional[str] = None
    close_order_id: Optional[str] = None

    position_side: Optional[str] = None
    leverage: Optional[int] = None

    initial_quote_size_usd: Optional[float] = None
    quote_size_before_usd: float
    quote_size_after_usd: float
    quote_delta_usd: float

    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: Optional[float] = None

    realized_gross_pnl_usd: float = 0.0
    realized_net_pnl_usd: float = 0.0

    fee_open_estimated_usd: float = 0.0
    fee_close_estimated_usd: float = 0.0
    fee_total_estimated_usd: float = 0.0
    taker_fee_rate: float = 0.0

    close_reason: Optional[str] = None

    opened_at: Optional[int] = None
    opened_at_iso: Optional[str] = None
    closed_at: Optional[int] = None
    closed_at_iso: Optional[str] = None

    model_config = ConfigDict(extra="ignore")