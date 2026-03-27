from __future__ import annotations

import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import Any, Optional

from binance.client import Client

from config.settings import settings


class BinanceFuturesClient:
    """
    Thin async wrapper around the Binance futures client.

    This client is responsible only for exchange interaction and small
    exchange-specific quantity normalization helpers.
    """

    def __init__(self) -> None:
        """
        Initialize the Binance futures client.
        """
        self._client = Client(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=settings.BINANCE_TESTNET,
            tld=settings.BINANCE_TLD,
        )
        self._exchange_info_cache: dict[str, dict[str, Any]] = {}

    async def ping(self) -> dict[str, Any]:
        """
        Ping Binance to validate connectivity.
        """
        return await asyncio.to_thread(self._client.ping)

    async def get_symbol_price(self, symbol: str) -> float:
        """
        Get the current futures mark price for a symbol.
        """
        payload = await asyncio.to_thread(self._client.futures_mark_price, symbol=str(symbol).upper())
        return float(payload["markPrice"])

    async def get_min_notional(self, symbol: str) -> float:
        """
        Get the minimum notional required by Binance for a symbol.
        """
        filters = await self._get_symbol_filters(symbol)
        return float(filters["min_notional"])

    async def change_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        """
        Set leverage for a symbol.
        """
        return await asyncio.to_thread(
            self._client.futures_change_leverage,
            symbol=str(symbol).upper(),
            leverage=int(leverage),
        )

    async def open_market_position(
        self,
        *,
        symbol: str,
        position_side: str,
        quantity: float,
    ) -> dict[str, Any]:
        """
        Open a futures market position using hedge mode semantics.

        LONG uses BUY.
        SHORT uses SELL.
        """
        normalized_side = str(position_side).upper()
        side = "BUY" if normalized_side == "LONG" else "SELL"

        return await asyncio.to_thread(
            self._client.futures_create_order,
            symbol=str(symbol).upper(),
            side=side,
            type="MARKET",
            quantity=self._format_quantity(quantity),
            positionSide=normalized_side,
            recvWindow=settings.DEFAULT_RECV_WINDOW_MS,
        )

    async def close_market_position(
        self,
        *,
        symbol: str,
        position_side: str,
        quantity: float,
    ) -> dict[str, Any]:
        """
        Close a futures market position using hedge mode semantics.

        LONG closes with SELL.
        SHORT closes with BUY.
        """
        normalized_side = str(position_side).upper()
        side = "SELL" if normalized_side == "LONG" else "BUY"

        return await asyncio.to_thread(
            self._client.futures_create_order,
            symbol=str(symbol).upper(),
            side=side,
            type="MARKET",
            quantity=self._format_quantity(quantity),
            positionSide=normalized_side,
            recvWindow=settings.DEFAULT_RECV_WINDOW_MS,
        )

    async def get_position_snapshot(
        self,
        *,
        symbol: str,
        position_side: str,
    ) -> Optional[dict[str, Any]]:
        """
        Get current position snapshot for one symbol and hedge side.
        """
        positions = await asyncio.to_thread(
            self._client.futures_position_information,
            symbol=str(symbol).upper(),
        )
        normalized_side = str(position_side).upper()

        for item in positions:
            if str(item.get("positionSide", "")).upper() == normalized_side:
                return item
        return None

    async def normalize_quantity_from_quote_usd(
        self,
        *,
        symbol: str,
        quote_size_usd: float,
        price: float,
    ) -> float:
        """
        Convert quote notional in USD into normalized order quantity.

        This method validates both quantity rules and notional rules before the
        order is sent to Binance, so deterministic exchange rejections can be
        prevented earlier.
        """
        filters = await self._get_symbol_filters(symbol)

        step_size = Decimal(str(filters["step_size"]))
        min_qty = Decimal(str(filters["min_qty"]))
        max_qty = Decimal(str(filters["max_qty"])) if filters["max_qty"] is not None else None
        min_notional = float(filters["min_notional"])

        raw_qty = Decimal(str(float(quote_size_usd) / float(price)))
        normalized = (raw_qty / step_size).to_integral_value(rounding=ROUND_DOWN) * step_size

        if normalized < min_qty:
            raise ValueError(
                f"normalized quantity is below exchange minimum quantity for {str(symbol).upper()}: "
                f"requires >= {min_qty}, got {normalized}"
            )

        if max_qty is not None and normalized > max_qty:
            raise ValueError(
                f"normalized quantity is above exchange maximum quantity for {str(symbol).upper()}: "
                f"requires <= {max_qty}, got {normalized}"
            )

        normalized_notional = float(normalized) * float(price)
        if min_notional > 0.0 and normalized_notional < min_notional:
            raise ValueError(
                f"normalized order notional below exchange minimum for {str(symbol).upper()}: "
                f"requires >= {min_notional:.8f}, got {normalized_notional:.8f}. "
                f"Increase execution profile quote_size_usd."
            )

        return float(normalized)

    async def _get_symbol_filters(self, symbol: str) -> dict[str, Any]:
        """
        Read and cache exchange filters needed for quantity normalization.
        """
        normalized_symbol = str(symbol).upper()
        if normalized_symbol in self._exchange_info_cache:
            return self._exchange_info_cache[normalized_symbol]

        payload = await asyncio.to_thread(self._client.futures_exchange_info)
        symbols = payload.get("symbols", []) if isinstance(payload, dict) else []

        for item in symbols:
            if str(item.get("symbol", "")).upper() != normalized_symbol:
                continue

            market_lot_size = None
            lot_size = None
            min_notional: Optional[float] = None

            for f in item.get("filters", []):
                filter_type = str(f.get("filterType", "")).upper()

                if filter_type == "MARKET_LOT_SIZE":
                    market_lot_size = f
                    continue

                if filter_type == "LOT_SIZE":
                    lot_size = f
                    continue

                if filter_type in {"MIN_NOTIONAL", "NOTIONAL"}:
                    candidate = f.get("notional")
                    if candidate is None:
                        candidate = f.get("minNotional")
                    if candidate is not None:
                        min_notional = float(candidate)

            chosen_lot = market_lot_size or lot_size
            if not chosen_lot:
                raise RuntimeError(f"LOT_SIZE filter not found for symbol {normalized_symbol}")

            if min_notional is None:
                min_notional = float(getattr(settings, "BINANCE_FUTURES_DEFAULT_MIN_NOTIONAL", 100.0) or 100.0)

            out = {
                "step_size": float(chosen_lot["stepSize"]),
                "min_qty": float(chosen_lot["minQty"]),
                "max_qty": (
                    float(chosen_lot["maxQty"])
                    if chosen_lot.get("maxQty") not in (None, "", "0")
                    else None
                ),
                "min_notional": float(min_notional),
            }
            self._exchange_info_cache[normalized_symbol] = out
            return out

        raise RuntimeError(f"symbol not found in exchange info: {normalized_symbol}")

    def _format_quantity(self, quantity: float) -> str:
        """
        Format a quantity for Binance REST requests.
        """
        return format(Decimal(str(quantity)).normalize(), "f")