from __future__ import annotations

import numpy as np
import pandas as pd

from .models import Bar


def compute(bars: list[Bar]) -> pd.DataFrame:
    frame = pd.DataFrame([b.__dict__ for b in bars])
    close = frame["close"]
    frame["ret"] = close.pct_change()
    frame["ema_fast"] = close.ewm(span=12, adjust=False).mean()
    frame["ema_slow"] = close.ewm(span=26, adjust=False).mean()
    frame["macd"] = frame["ema_fast"] - frame["ema_slow"]
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    frame["rsi"] = (100 - (100 / (1 + rs))).where(loss > 0, 100.0).where(gain > 0, 0.0)
    mid = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    frame["bb_z"] = (close - mid) / std.replace(0, 1e-12)
    tr = pd.concat([(frame.high - frame.low), (frame.high - close.shift()).abs(), (frame.low - close.shift()).abs()], axis=1).max(axis=1)
    frame["atr"] = tr.rolling(14).mean()
    frame["volatility"] = frame.ret.rolling(30).std().fillna(0) * np.sqrt(365 * 24 * 60 / 15)
    frame["vwap"] = ((close * frame.volume).cumsum() / frame.volume.cumsum().replace(0, np.nan))
    return frame.replace([np.inf, -np.inf], np.nan).dropna()
