from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    symbol: str = os.getenv("NOVA_SYMBOL", "BTC/USD")
    interval_minutes: int = int(os.getenv("NOVA_INTERVAL_MINUTES", "15"))
    cycle_seconds: int = int(os.getenv("NOVA_CYCLE_SECONDS", "900"))
    max_cycles: int = int(os.getenv("NOVA_MAX_CYCLES", "96"))
    provider: str = os.getenv("NOVA_PROVIDER", "kraken")
    database: Path = Path(os.getenv("NOVA_DATABASE", "runtime/nova.db"))
    progress_file: Path = Path(os.getenv("NOVA_PROGRESS_FILE", "runtime/progress.json"))
    vault: Path = Path(os.getenv("NOVA_VAULT", "runtime/vault"))
    bind_host: str = os.getenv("NOVA_BIND_HOST", "127.0.0.1")
    bind_port: int = int(os.getenv("NOVA_BIND_PORT", "8765"))
    max_notional_usd: float = float(os.getenv("NOVA_MAX_NOTIONAL_USD", "100"))
    max_daily_risk_usd: float = float(os.getenv("NOVA_MAX_DAILY_RISK_USD", "10"))
    max_drawdown_pct: float = float(os.getenv("NOVA_MAX_DRAWDOWN_PCT", "5"))

    def prepare(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        for folder in ("Decisions", "Strategies", "Performance", "Logs"):
            (self.vault / folder).mkdir(parents=True, exist_ok=True)
