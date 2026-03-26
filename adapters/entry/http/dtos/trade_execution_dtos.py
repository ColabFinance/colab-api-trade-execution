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
    leverage: int
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