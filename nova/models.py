from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Bar:
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Decision:
    decision_id: str
    timestamp: str
    symbol: str
    action: Literal["buy", "sell", "hold"]
    confidence: float
    reference_price: float
    notional_usd: float
    stop_price: float | None
    take_profit_price: float | None
    strategy_version: str
    rationale: str
    data_sha256: str
    status: Literal["proposed", "blocked"] = "proposed"

    def to_dict(self) -> dict:
        return asdict(self)

