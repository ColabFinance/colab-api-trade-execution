from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from adapters.external.binance.binance_futures_client import BinanceFuturesClient
from core.domain.entities.execution_profile_entity import ExecutionProfileEntity
from core.domain.entities.trade_order_entity import TradeOrderEntity
from core.domain.entities.trade_position_entity import TradePositionEntity
from core.repositories.execution_profile_repository import ExecutionProfileRepository
from core.repositories.trade_order_repository import TradeOrderRepository
from core.repositories.trade_position_repository import TradePositionRepository


class TradeExecutionUseCase:
    """
    Main application use case for api-trade-execution.

    This use case manages:
    - execution profiles
    - open position execution
    - close position execution
    - persisted orders and positions
    """

    def __init__(
        self,
        *,
        profile_repo: ExecutionProfileRepository,
        position_repo: TradePositionRepository,
        order_repo: TradeOrderRepository,
        binance_client: BinanceFuturesClient,
    ) -> None:
        """
        Initialize the trade execution use case.
        """
        self._profile_repo = profile_repo
        self._position_repo = position_repo
        self._order_repo = order_repo
        self._binance = binance_client

    async def ensure_indexes(self) -> None:
        """
        Ensure indexes required by all repositories.
        """
        await self._profile_repo.ensure_indexes()
        await self._position_repo.ensure_indexes()
        await self._order_repo.ensure_indexes()

    async def upsert_execution_profile(
        self,
        *,
        execution_account_id: str,
        symbol: str,
        is_enabled: bool,
        quote_size_usd: float,
        leverage: int,
    ) -> ExecutionProfileEntity:
        """
        Upsert an execution profile document.

        The profile is validated against Binance symbol rules before it is saved,
        which avoids deterministic runtime failures later.
        """
        normalized_symbol = str(symbol).strip().upper()
        normalized_quote_size_usd = float(quote_size_usd)

        await self._validate_profile_quote_size(
            symbol=normalized_symbol,
            quote_size_usd=normalized_quote_size_usd,
        )

        entity = ExecutionProfileEntity(
            execution_account_id=str(execution_account_id).strip(),
            symbol=normalized_symbol,
            is_enabled=bool(is_enabled),
            quote_size_usd=normalized_quote_size_usd,
            leverage=int(leverage),
        )
        return await self._profile_repo.upsert(entity)

    async def list_execution_profiles(
        self,
        execution_account_id: Optional[str] = None,
    ):
        """
        List execution profiles.
        """
        return await self._profile_repo.list(execution_account_id=execution_account_id)

    async def open_position(
        self,
        *,
        strategy_id: str,
        execution_account_id: str,
        symbol: str,
        position_side: str,
        signal_id: Optional[str],
        signal_ts: Optional[int],
        signal_type: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """
        Open a market position on Binance futures.

        This method is idempotent by `idempotency_key`.
        """
        existing_order = await self._order_repo.get_by_idempotency_key(idempotency_key)
        if existing_order is not None:
            active_position = await self._position_repo.get_active_by_strategy(
                strategy_id=strategy_id,
                execution_account_id=execution_account_id,
                symbol=symbol,
            )
            return {
                "ok": True,
                "executed": False,
                "reason": "IDEMPOTENT_REPLAY",
                "order": existing_order.model_dump(),
                "position": active_position.model_dump() if active_position else None,
            }

        profile = await self._profile_repo.get_by_account_symbol(
            execution_account_id=execution_account_id,
            symbol=symbol,
        )
        if profile is None:
            raise ValueError("execution profile not found")
        if not profile.is_enabled:
            raise ValueError("execution profile is disabled")

        active_position = await self._position_repo.get_active_by_strategy(
            strategy_id=strategy_id,
            execution_account_id=execution_account_id,
            symbol=symbol,
        )
        if active_position is not None:
            if str(active_position.position_side).upper() == str(position_side).upper():
                return {
                    "ok": True,
                    "executed": False,
                    "reason": "POSITION_ALREADY_OPEN_SAME_SIDE",
                    "position": active_position.model_dump(),
                }
            raise ValueError("active position exists with different side")

        current_price = await self._binance.get_symbol_price(symbol=symbol)
        quantity = await self._binance.normalize_quantity_from_quote_usd(
            symbol=symbol,
            quote_size_usd=profile.quote_size_usd,
            price=current_price,
        )

        await self._binance.change_leverage(symbol=symbol, leverage=profile.leverage)

        raw_order = await self._binance.open_market_position(
            symbol=symbol,
            position_side=position_side,
            quantity=quantity,
        )

        now_ms, now_iso = self._now()
        position_snapshot = await self._binance.get_position_snapshot(
            symbol=symbol,
            position_side=position_side,
        )

        entry_price = float(position_snapshot.get("entryPrice") or current_price) if position_snapshot else float(current_price)
        position_qty = abs(float(position_snapshot.get("positionAmt") or quantity)) if position_snapshot else float(quantity)

        order = TradeOrderEntity(
            action="OPEN",
            idempotency_key=str(idempotency_key),
            strategy_id=str(strategy_id),
            execution_account_id=str(execution_account_id).strip(),
            symbol=str(symbol).strip().upper(),
            position_side=str(position_side).strip().upper(),
            side="BUY" if str(position_side).upper() == "LONG" else "SELL",
            quantity=float(quantity),
            signal_id=signal_id,
            signal_ts=signal_ts,
            binance_order_id=str(raw_order.get("orderId")) if raw_order.get("orderId") is not None else None,
            status=str(raw_order.get("status") or "SENT"),
            raw_response=raw_order,
        )
        stored_order = await self._order_repo.insert(order)

        position = TradePositionEntity(
            strategy_id=str(strategy_id),
            execution_account_id=str(execution_account_id).strip(),
            symbol=str(symbol).strip().upper(),
            position_side=str(position_side).strip().upper(),
            status="OPEN",
            quantity=float(position_qty),
            entry_price=float(entry_price),
            open_order_id=stored_order.binance_order_id,
            signal_open_id=signal_id,
            open_reason=str(signal_type),
            opened_at=int(now_ms),
            opened_at_iso=str(now_iso),
        )
        stored_position = await self._position_repo.upsert_open(position)

        return {
            "ok": True,
            "executed": True,
            "order": stored_order.model_dump(),
            "position": stored_position.model_dump(),
        }

    async def close_position(
        self,
        *,
        strategy_id: str,
        execution_account_id: str,
        symbol: str,
        close_reason: str,
        signal_id: Optional[str],
        signal_ts: Optional[int],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """
        Close the active position for one strategy/account/symbol.

        This method is idempotent by `idempotency_key`.
        """
        existing_order = await self._order_repo.get_by_idempotency_key(idempotency_key)
        if existing_order is not None:
            active_position = await self._position_repo.get_active_by_strategy(
                strategy_id=strategy_id,
                execution_account_id=execution_account_id,
                symbol=symbol,
            )
            return {
                "ok": True,
                "executed": False,
                "reason": "IDEMPOTENT_REPLAY",
                "order": existing_order.model_dump(),
                "position": active_position.model_dump() if active_position else None,
            }

        active_position = await self._position_repo.get_active_by_strategy(
            strategy_id=strategy_id,
            execution_account_id=execution_account_id,
            symbol=symbol,
        )
        if active_position is None:
            return {
                "ok": True,
                "executed": False,
                "reason": "NO_ACTIVE_POSITION",
            }

        raw_order = await self._binance.close_market_position(
            symbol=symbol,
            position_side=active_position.position_side,
            quantity=active_position.quantity,
        )

        exit_price = await self._binance.get_symbol_price(symbol=symbol)
        now_ms, now_iso = self._now()

        order = TradeOrderEntity(
            action="CLOSE",
            idempotency_key=str(idempotency_key),
            strategy_id=str(strategy_id),
            execution_account_id=str(execution_account_id).strip(),
            symbol=str(symbol).strip().upper(),
            position_side=str(active_position.position_side).strip().upper(),
            side="SELL" if str(active_position.position_side).upper() == "LONG" else "BUY",
            quantity=float(active_position.quantity),
            signal_id=signal_id,
            signal_ts=signal_ts,
            binance_order_id=str(raw_order.get("orderId")) if raw_order.get("orderId") is not None else None,
            status=str(raw_order.get("status") or "SENT"),
            raw_response=raw_order,
        )
        stored_order = await self._order_repo.insert(order)

        closed_position = await self._position_repo.mark_closed(
            position_id=str(active_position.id),
            close_order_id=str(stored_order.binance_order_id or ""),
            close_reason=str(close_reason),
            signal_close_id=signal_id,
            closed_at=int(now_ms),
            closed_at_iso=str(now_iso),
            exit_price=float(exit_price),
        )

        return {
            "ok": True,
            "executed": True,
            "order": stored_order.model_dump(),
            "position": closed_position.model_dump() if closed_position else None,
        }

    async def list_active_positions(
        self,
        execution_account_id: Optional[str] = None,
    ):
        """
        List active positions.
        """
        return await self._position_repo.list_active(execution_account_id=execution_account_id)

    async def list_orders_by_strategy_id(
        self,
        strategy_id: str,
        limit: int,
    ):
        """
        List order history for one strategy.
        """
        return await self._order_repo.list_by_strategy_id(strategy_id=strategy_id, limit=int(limit))

    async def _validate_profile_quote_size(
        self,
        *,
        symbol: str,
        quote_size_usd: float,
    ) -> None:
        """
        Validate that the configured execution size is acceptable for Binance.

        This prevents saving profiles that are guaranteed to fail later.
        """
        if float(quote_size_usd) <= 0.0:
            raise ValueError("quote_size_usd must be greater than zero")

        min_notional = await self._binance.get_min_notional(symbol=symbol)
        if min_notional > 0.0 and float(quote_size_usd) < float(min_notional):
            raise ValueError(
                f"quote_size_usd below exchange minimum notional for {str(symbol).upper()}: "
                f"requires >= {float(min_notional):.8f}, got {float(quote_size_usd):.8f}"
            )

        current_price = await self._binance.get_symbol_price(symbol=symbol)
        await self._binance.normalize_quantity_from_quote_usd(
            symbol=symbol,
            quote_size_usd=float(quote_size_usd),
            price=float(current_price),
        )

    def _now(self) -> tuple[int, str]:
        """
        Return current UTC time in milliseconds and ISO string.
        """
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return now_ms, now_iso