from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Signal:
    action: str
    score: float
    confidence: float
    rationale: str


class EnsembleStrategy:
    version = "ensemble-1.0.0"

    def evaluate(self, frame: pd.DataFrame) -> Signal:
        row = frame.iloc[-1]
        trend = float(np.tanh((row.ema_fast / row.ema_slow - 1) * 120))
        momentum = float(np.tanh(row.macd / max(row.atr, 1e-9)))
        mean_reversion = float(np.clip(-row.bb_z / 2.5, -1, 1))
        rsi = float(np.clip((50 - row.rsi) / 30, -1, 1))
        score = 0.40 * trend + 0.25 * momentum + 0.20 * mean_reversion + 0.15 * rsi
        confidence = min(1.0, abs(score))
        action = "hold" if abs(score) < 0.28 else ("buy" if score > 0 else "sell")
        rationale = (
            f"trend={trend:.3f}; momentum={momentum:.3f}; mean_reversion={mean_reversion:.3f}; "
            f"rsi_component={rsi:.3f}; ensemble={score:.3f}; rsi={row.rsi:.2f}; atr={row.atr:.2f}"
        )
        return Signal(action, score, confidence, rationale)

