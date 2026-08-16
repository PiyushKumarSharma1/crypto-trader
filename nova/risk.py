from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    notional_usd: float
    stop_price: float | None
    take_profit_price: float | None
    reason: str


class RiskManager:
    def __init__(self, max_notional: float, max_daily_risk: float, max_drawdown_pct: float) -> None:
        self.max_notional = max_notional
        self.max_daily_risk = max_daily_risk
        self.max_drawdown_pct = max_drawdown_pct

    def size(self, action: str, confidence: float, price: float, atr: float, daily_loss: float = 0, drawdown_pct: float = 0) -> RiskDecision:
        if action == "hold":
            return RiskDecision(False, 0, None, None, "signal below decision threshold")
        if daily_loss >= self.max_daily_risk:
            return RiskDecision(False, 0, None, None, "daily risk budget exhausted")
        if drawdown_pct >= self.max_drawdown_pct:
            return RiskDecision(False, 0, None, None, "drawdown circuit breaker active")
        risk_fraction = min(0.25, max(0.02, confidence * 0.20))
        notional = round(self.max_notional * risk_fraction, 2)
        distance = max(atr * 1.5, price * 0.003)
        stop = price - distance if action == "buy" else price + distance
        take = price + distance * 2 if action == "buy" else price - distance * 2
        return RiskDecision(True, notional, round(stop, 2), round(take, 2), "within configured risk envelope")

