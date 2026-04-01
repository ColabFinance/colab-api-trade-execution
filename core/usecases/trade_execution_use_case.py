from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from adapters.external.binance.binance_futures_client import BinanceFuturesClient
from config.settings import settings
from core.domain.entities.execution_profile_entity import ExecutionProfileEntity
from core.domain.entities.execution_profile_quote_history_entity import (
    ExecutionProfileQuoteHistoryEntity,
)
from core.domain.entities.trade_order_entity import TradeOrderEntity
from core.domain.entities.trade_position_entity import TradePositionEntity
from core.repositories.execution_profile_quote_history_repository import (
    ExecutionProfileQuoteHistoryRepository,
)
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
    - dynamic quote resizing after realized PnL
    """

    def __init__(
        self,
        *,
        profile_repo: ExecutionProfileRepository,
        profile_quote_history_repo: ExecutionProfileQuoteHistoryRepository,
        position_repo: TradePositionRepository,
        order_repo: TradeOrderRepository,
        binance_client: BinanceFuturesClient,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the trade execution use case.
        """
        self._profile_repo = profile_repo
        self._profile_quote_history_repo = profile_quote_history_repo
        self._position_repo = position_repo
        self._order_repo = order_repo
        self._binance = binance_client
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    async def ensure_indexes(self) -> None:
        """
        Ensure indexes required by all repositories.
        """
        await self._profile_repo.ensure_indexes()
        await self._profile_quote_history_repo.ensure_indexes()
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

        existing = await self._profile_repo.get_by_account_symbol(
            execution_account_id=str(execution_account_id).strip(),
            symbol=normalized_symbol,
        )

        entity = ExecutionProfileEntity(
            execution_account_id=str(execution_account_id).strip(),
            symbol=normalized_symbol,
            is_enabled=bool(is_enabled),
            quote_size_usd=normalized_quote_size_usd,
            initial_quote_size_usd=(
                float(existing.initial_quote_size_usd)
                if existing is not None and existing.initial_quote_size_usd is not None
                else normalized_quote_size_usd
            ),
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

        profile = await self._profile_repo.get_by_account_symbol(
            execution_account_id=execution_account_id,
            symbol=symbol,
        )

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

        if profile is not None and closed_position is not None:
            try:
                await self._apply_dynamic_quote_update(
                    profile=profile,
                    position=closed_position,
                    strategy_id=str(strategy_id),
                    close_order_id=str(stored_order.binance_order_id or ""),
                    close_reason=str(close_reason),
                )
            except Exception as exc:
                self._logger.warning(
                    "Quote auto-update failed after close. execution_account_id=%s symbol=%s strategy_id=%s err=%s",
                    execution_account_id,
                    symbol,
                    strategy_id,
                    exc,
                )

        return {
            "ok": True,
            "executed": True,
            "order": stored_order.model_dump(),
            "position": closed_position.model_dump() if closed_position else None,
        }

    async def list_quote_history_paginated(
        self,
        *,
        execution_account_id: str,
        symbol: str,
        limit: int = 20,
        page: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> dict:
        """
        List dynamic quote adjustment history for one execution profile.
        """
        resolved_limit = int(limit)
        resolved_offset = int(offset or 0)

        if page is not None:
            resolved_page = max(1, int(page))
            resolved_offset = (resolved_page - 1) * resolved_limit
        else:
            resolved_page = (resolved_offset // resolved_limit) + 1

        items = await self._profile_quote_history_repo.list_paginated(
            execution_account_id=str(execution_account_id).strip(),
            symbol=str(symbol).strip().upper(),
            limit=resolved_limit,
            offset=resolved_offset,
        )
        total = await self._profile_quote_history_repo.count(
            execution_account_id=str(execution_account_id).strip(),
            symbol=str(symbol).strip().upper(),
        )

        return {
            "items": items,
            "pagination": {
                "limit": resolved_limit,
                "offset": resolved_offset,
                "page": resolved_page,
                "total": int(total),
                "has_next": (resolved_offset + resolved_limit) < int(total),
                "has_prev": resolved_offset > 0,
            },
        }

    async def list_active_positions(
        self,
        execution_account_id: Optional[str] = None,
    ):
        """
        List active positions.
        """
        return await self._position_repo.list_active(execution_account_id=execution_account_id)

    async def list_positions_paginated(
        self,
        *,
        execution_account_id: Optional[str] = None,
        status_scope: str = "OPEN",
        limit: int = 10,
        page: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> dict:
        normalized_scope = str(status_scope or "OPEN").strip().upper()
        if normalized_scope not in {"ALL", "OPEN", "CLOSED"}:
            raise ValueError("status_scope must be ALL, OPEN or CLOSED")

        resolved_limit = int(limit)
        resolved_offset = int(offset or 0)

        if page is not None:
            resolved_page = max(1, int(page))
            resolved_offset = (resolved_page - 1) * resolved_limit
        else:
            resolved_page = (resolved_offset // resolved_limit) + 1

        items = await self._position_repo.list_paginated(
            execution_account_id=execution_account_id,
            status_scope=normalized_scope,
            limit=resolved_limit,
            offset=resolved_offset,
        )
        total = await self._position_repo.count(
            execution_account_id=execution_account_id,
            status_scope=normalized_scope,
        )

        return {
            "items": items,
            "pagination": {
                "limit": resolved_limit,
                "offset": resolved_offset,
                "page": resolved_page,
                "total": int(total),
                "has_next": (resolved_offset + resolved_limit) < int(total),
                "has_prev": resolved_offset > 0,
            },
        }

    async def list_orders_by_strategy_id(
        self,
        strategy_id: str,
        limit: int,
    ):
        """
        List order history for one strategy.
        """
        return await self._order_repo.list_by_strategy_id(strategy_id=strategy_id, limit=int(limit))

    async def list_orders_paginated(
        self,
        *,
        strategy_id: Optional[str] = None,
        execution_account_id: Optional[str] = None,
        lifecycle_scope: str = "OPEN",
        limit: int = 10,
        page: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> dict:
        normalized_scope = str(lifecycle_scope or "OPEN").strip().upper()
        if normalized_scope not in {"ALL", "OPEN", "CLOSED"}:
            raise ValueError("lifecycle_scope must be ALL, OPEN or CLOSED")

        resolved_limit = int(limit)
        resolved_offset = int(offset or 0)

        if page is not None:
            resolved_page = max(1, int(page))
            resolved_offset = (resolved_page - 1) * resolved_limit
        else:
            resolved_page = (resolved_offset // resolved_limit) + 1

        items = await self._order_repo.list_paginated(
            strategy_id=strategy_id,
            execution_account_id=execution_account_id,
            lifecycle_scope=normalized_scope,
            limit=resolved_limit,
            offset=resolved_offset,
        )
        total = await self._order_repo.count(
            strategy_id=strategy_id,
            execution_account_id=execution_account_id,
            lifecycle_scope=normalized_scope,
        )

        return {
            "items": items,
            "pagination": {
                "limit": resolved_limit,
                "offset": resolved_offset,
                "page": resolved_page,
                "total": int(total),
                "has_next": (resolved_offset + resolved_limit) < int(total),
                "has_prev": resolved_offset > 0,
            },
        }

    async def _apply_dynamic_quote_update(
        self,
        *,
        profile: ExecutionProfileEntity,
        position: TradePositionEntity,
        strategy_id: str,
        close_order_id: str,
        close_reason: str,
    ) -> None:
        """
        Recalculate the profile quote after a realized trade close and persist
        a history row for that adjustment.

        The update formula is:

            new_quote = max(0, current_quote + realized_net_pnl)

        Fees are stored as estimated taker fees using the configured/fallback
        taker rate. This avoids depending on extra Binance trade-fill calls.
        """
        entry_price = float(position.entry_price)
        exit_price = float(position.exit_price or 0.0)
        quantity = float(position.quantity)
        current_quote = float(profile.quote_size_usd)
        initial_quote = float(profile.initial_quote_size_usd or profile.quote_size_usd)

        side = str(position.position_side).strip().upper()
        if side == "LONG":
            gross_pnl_usd = (exit_price - entry_price) * quantity
        else:
            gross_pnl_usd = (entry_price - exit_price) * quantity

        taker_fee_rate = self._get_taker_fee_rate()

        open_notional = float(entry_price * quantity)
        close_notional = float(exit_price * quantity)

        fee_open_estimated_usd = float(open_notional * taker_fee_rate)
        fee_close_estimated_usd = float(close_notional * taker_fee_rate)
        fee_total_estimated_usd = float(fee_open_estimated_usd + fee_close_estimated_usd)

        realized_net_pnl_usd = float(gross_pnl_usd - fee_total_estimated_usd)

        new_quote_size_usd = max(0.0, float(current_quote + realized_net_pnl_usd))
        quote_delta_usd = float(new_quote_size_usd - current_quote)

        await self._profile_repo.update_quote_size(
            execution_account_id=profile.execution_account_id,
            symbol=profile.symbol,
            quote_size_usd=new_quote_size_usd,
        )

        history = ExecutionProfileQuoteHistoryEntity(
            execution_account_id=str(profile.execution_account_id).strip(),
            symbol=str(profile.symbol).strip().upper(),
            strategy_id=str(strategy_id),
            position_id=str(position.id) if position.id is not None else None,
            close_order_id=str(close_order_id) if close_order_id else None,
            position_side=side,
            leverage=int(profile.leverage),
            initial_quote_size_usd=float(initial_quote),
            quote_size_before_usd=float(current_quote),
            quote_size_after_usd=float(new_quote_size_usd),
            quote_delta_usd=float(quote_delta_usd),
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            quantity=float(quantity),
            realized_gross_pnl_usd=float(gross_pnl_usd),
            realized_net_pnl_usd=float(realized_net_pnl_usd),
            fee_open_estimated_usd=float(fee_open_estimated_usd),
            fee_close_estimated_usd=float(fee_close_estimated_usd),
            fee_total_estimated_usd=float(fee_total_estimated_usd),
            taker_fee_rate=float(taker_fee_rate),
            close_reason=str(close_reason),
            opened_at=position.opened_at,
            opened_at_iso=position.opened_at_iso,
            closed_at=position.closed_at,
            closed_at_iso=position.closed_at_iso,
        )
        await self._profile_quote_history_repo.insert(history)

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

    def _get_taker_fee_rate(self) -> float:
        """
        Return the taker fee rate used for estimated fee accounting.

        Default fallback:
        - 0.0005 = 0.05% per side
        - open + close ~= 0.10%
        """
        return float(getattr(settings, "BINANCE_FUTURES_TAKER_FEE_RATE", 0.0005) or 0.0005)

    def _now(self) -> tuple[int, str]:
        """
        Return current UTC time in milliseconds and ISO string.
        """
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return now_ms, now_iso