from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import asdict

import httpx

from .models import Bar


class MarketDataError(RuntimeError):
    pass


class MarketDataClient:
    def __init__(self, timeout: float = 12.0, attempts: int = 3) -> None:
        self.timeout = timeout
        self.attempts = attempts

    async def fetch(self, provider: str, symbol: str, interval_minutes: int, limit: int = 240) -> list[Bar]:
        provider = provider.lower()
        if provider == "hyperliquid":
            return await self._hyperliquid(symbol, interval_minutes, limit)
        return await self._kraken(symbol, interval_minutes, limit)

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        last: Exception | None = None
        for attempt in range(self.attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "nova-market-control/0.1"}) as client:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
                await asyncio.sleep(0.5 * (2**attempt))
        raise MarketDataError(f"market data request failed after {self.attempts} attempts: {last}")

    async def _kraken(self, symbol: str, interval: int, limit: int) -> list[Bar]:
        pair = {"BTC/USD": "XBTUSD", "ETH/USD": "ETHUSD"}.get(symbol, symbol.replace("/", ""))
        payload = await self._request("GET", "https://api.kraken.com/0/public/OHLC", params={"pair": pair, "interval": interval})
        if payload.get("error"):
            raise MarketDataError(f"Kraken error: {payload['error']}")
        result = payload.get("result", {})
        rows = next((value for key, value in result.items() if key != "last"), [])
        bars = [Bar(int(r[0]) * 1000, *map(float, (r[1], r[2], r[3], r[4], r[6]))) for r in rows[-limit:]]
        if len(bars) < 60:
            raise MarketDataError(f"insufficient Kraken bars: {len(bars)}")
        return bars

    async def _hyperliquid(self, symbol: str, interval: int, limit: int) -> list[Bar]:
        end = int(time.time() * 1000)
        start = end - limit * interval * 60_000
        coin = symbol.split("/")[0]
        body = {"type": "candleSnapshot", "req": {"coin": coin, "interval": f"{interval}m", "startTime": start, "endTime": end}}
        rows = await self._request("POST", "https://api.hyperliquid.xyz/info", json=body)
        bars = [Bar(int(r["t"]), *map(float, (r["o"], r["h"], r["l"], r["c"], r["v"]))) for r in rows]
        if len(bars) < 60:
            raise MarketDataError(f"insufficient Hyperliquid bars: {len(bars)}")
        return bars


def bars_digest(bars: list[Bar]) -> str:
    raw = json.dumps([asdict(b) for b in bars], separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()

