from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ExecutionProfileUpsertDTO(BaseModel):
    """
    DTO used to create or update one execution profile.
    """

    execution_account_id: str
    symbol: str
    is_enabled: bool = True
    quote_size_usd: float = Field(..., gt=0)
    leverage: int = Field(..., ge=1)

    @field_validator("execution_account_id", "symbol")
    @classmethod
    def _strip_required_strings(cls, v: str) -> str:
        """
        Normalize required strings.
        """
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required")
        return v

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        """
        Normalize symbol to uppercase.
        """
        return str(v).strip().upper()


class ExecutionProfileOutDTO(BaseModel):
    """
    DTO returned when reading one execution profile.
    """

    id: Optional[str] = None
    execution_account_id: str
    symbol: str
    is_enabled: bool
    quote_size_usd: float
    initial_quote_size_usd: Optional[float] = None
    leverage: int
    created_at: Optional[int] = None
    created_at_iso: Optional[str] = None
    updated_at: Optional[int] = None
    updated_at_iso: Optional[str] = None


class ExecutionProfileQuoteHistoryOutDTO(BaseModel):
    """
    DTO returned when reading quote-size change history for one execution profile.
    """

    id: Optional[str] = None

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

    created_at: Optional[int] = None
    created_at_iso: Optional[str] = None
    updated_at: Optional[int] = None
    updated_at_iso: Optional[str] = None


class TradeOpenRequestDTO(BaseModel):
    """
    DTO used by internal callers to request a market open.
    """

    strategy_id: str
    execution_account_id: str
    symbol: str
    position_side: str
    signal_id: Optional[str] = None
    signal_ts: Optional[int] = None
    signal_type: str
    idempotency_key: str

    @field_validator("strategy_id", "execution_account_id", "symbol", "position_side", "signal_type", "idempotency_key")
    @classmethod
    def _strip_required_strings(cls, v: str) -> str:
        """
        Normalize required strings.
        """
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required")
        return v

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        """
        Normalize symbol to uppercase.
        """
        return str(v).strip().upper()

    @field_validator("position_side")
    @classmethod
    def _normalize_side(cls, v: str) -> str:
        """
        Normalize position side.
        """
        normalized = str(v).strip().upper()
        if normalized not in {"LONG", "SHORT"}:
            raise ValueError("position_side must be LONG or SHORT")
        return normalized


class TradeCloseRequestDTO(BaseModel):
    """
    DTO used by internal callers to request a market close.
    """

    strategy_id: str
    execution_account_id: str
    symbol: str
    close_reason: str
    signal_id: Optional[str] = None
    signal_ts: Optional[int] = None
    idempotency_key: str

    @field_validator("strategy_id", "execution_account_id", "symbol", "close_reason", "idempotency_key")
    @classmethod
    def _strip_required_strings(cls, v: str) -> str:
        """
        Normalize required strings.
        """
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required")
        return v

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        """
        Normalize symbol to uppercase.
        """
        return str(v).strip().upper()


class TradeExecutionResponseDTO(BaseModel):
    """
    Generic response DTO for open and close trade execution endpoints.
    """

    ok: bool
    executed: bool
    reason: Optional[str] = None
    order: Optional[dict] = None
    position: Optional[dict] = None


class TradePositionListQueryDTO(BaseModel):
    """
    DTO for listing positions with filters and pagination.
    """

    execution_account_id: Optional[str] = None
    status_scope: str = "OPEN"
    limit: int = Field(default=10, ge=1, le=1000)
    page: Optional[int] = Field(default=None, ge=1)
    offset: Optional[int] = Field(default=None, ge=0)

    @field_validator("execution_account_id")
    @classmethod
    def _strip_optional_execution_account_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = str(v).strip()
        return value or None

    @field_validator("status_scope")
    @classmethod
    def _normalize_status_scope(cls, v: str) -> str:
        normalized = str(v or "OPEN").strip().upper()
        if normalized not in {"ALL", "OPEN", "CLOSED"}:
            raise ValueError("status_scope must be ALL, OPEN or CLOSED")
        return normalized


class TradeOrderListQueryDTO(BaseModel):
    """
    DTO for listing orders with filters and pagination.
    """

    strategy_id: Optional[str] = None
    execution_account_id: Optional[str] = None
    lifecycle_scope: str = "ALL"
    limit: int = Field(default=10, ge=1, le=1000)
    page: Optional[int] = Field(default=None, ge=1)
    offset: Optional[int] = Field(default=None, ge=0)

    @field_validator("strategy_id", "execution_account_id")
    @classmethod
    def _strip_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = str(v).strip()
        return value or None

    @field_validator("lifecycle_scope")
    @classmethod
    def _normalize_lifecycle_scope(cls, v: str) -> str:
        normalized = str(v or "ALL").strip().upper()
        if normalized not in {"ALL", "OPEN", "CLOSED"}:
            raise ValueError("lifecycle_scope must be ALL, OPEN or CLOSED")
        return normalized


class TradePaginationDTO(BaseModel):
    """
    Generic pagination DTO for trade list endpoints.
    """

    limit: int
    offset: int
    page: int
    total: int
    has_next: bool
    has_prev: bool


class TradePositionOutDTO(BaseModel):
    """
    DTO returned when reading trade positions.
    """

    id: Optional[str] = None
    strategy_id: str
    execution_account_id: str
    symbol: str
    position_side: str
    status: str
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
    created_at: Optional[int] = None
    created_at_iso: Optional[str] = None
    updated_at: Optional[int] = None
    updated_at_iso: Optional[str] = None


class TradeOrderOutDTO(BaseModel):
    """
    DTO returned when reading trade orders.
    """

    id: Optional[str] = None
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
    status: str
    raw_response: Optional[dict] = None
    created_at: Optional[int] = None
    created_at_iso: Optional[str] = None
    updated_at: Optional[int] = None
    updated_at_iso: Optional[str] = None


class TradePositionListResponseDTO(BaseModel):
    """
    Response DTO for positions listing.
    """

    ok: bool
    message: str
    data: list[TradePositionOutDTO]
    pagination: TradePaginationDTO


class TradeOrderListResponseDTO(BaseModel):
    """
    Response DTO for orders listing.
    """

    ok: bool
    message: str
    data: list[TradeOrderOutDTO]
    pagination: TradePaginationDTO