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
        Convert quote notional in USD into normalized MARKET order quantity.
        """
        raw_qty = float(quote_size_usd) / float(price)
        filters = await self._get_symbol_filters(symbol)

        step_size = Decimal(str(filters["step_size"]))
        min_qty = Decimal(str(filters["min_qty"]))
        max_qty = Decimal(str(filters["max_qty"]))

        qty = Decimal(str(raw_qty))
        normalized = (qty / step_size).to_integral_value(rounding=ROUND_DOWN) * step_size

        if normalized < min_qty:
            raise ValueError("normalized quantity is below exchange minimum quantity")
        if normalized > max_qty:
            raise ValueError("normalized quantity is above exchange maximum quantity")

        return float(normalized)

    async def _get_symbol_filters(self, symbol: str) -> dict[str, Any]:
        """
        Read and cache exchange filters needed for MARKET quantity normalization.
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

            for f in item.get("filters", []):
                filter_type = str(f.get("filterType", "")).upper()
                if filter_type == "MARKET_LOT_SIZE":
                    market_lot_size = f
                elif filter_type == "LOT_SIZE":
                    lot_size = f

            selected = market_lot_size or lot_size
            if not selected:
                raise RuntimeError(f"quantity filter not found for symbol {normalized_symbol}")

            out = {
                "step_size": float(selected["stepSize"]),
                "min_qty": float(selected["minQty"]),
                "max_qty": float(selected["maxQty"]),
            }
            self._exchange_info_cache[normalized_symbol] = out
            return out

        raise RuntimeError(f"symbol not found in exchange info: {normalized_symbol}")

    def _format_quantity(self, quantity: float) -> str:
        """
        Format a quantity for Binance REST requests.
        """
        return format(Decimal(str(quantity)).normalize(), "f")