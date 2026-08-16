from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid

from fastapi import FastAPI

from .config import Settings
from .indicators import compute
from .market_data import MarketDataClient, bars_digest
from .memory import VaultMemory
from .models import Decision, utc_now
from .risk import RiskManager
from .store import Store
from .strategy import EnsembleStrategy

log = logging.getLogger("nova")
settings = Settings()
settings.prepare()
store = Store(settings.database)
memory = VaultMemory(settings.vault)
app = FastAPI(title="Nova Market Control", version="0.1.0")


async def run_cycle() -> dict:
    started = utc_now()
    before = time.monotonic()
    try:
        bars = await MarketDataClient().fetch(settings.provider, settings.symbol, settings.interval_minutes)
        frame = compute(bars)
        if frame.empty:
            raise RuntimeError("indicator warm-up produced no rows")
        signal = EnsembleStrategy().evaluate(frame)
        row = frame.iloc[-1]
        risk = RiskManager(settings.max_notional_usd, settings.max_daily_risk_usd, settings.max_drawdown_pct).size(
            signal.action, signal.confidence, float(row.close), float(row.atr)
        )
        decision = Decision(
            decision_id=uuid.uuid4().hex[:12], timestamp=utc_now(), symbol=settings.symbol,
            action=signal.action, confidence=signal.confidence, reference_price=float(row.close),
            notional_usd=risk.notional_usd, stop_price=risk.stop_price, take_profit_price=risk.take_profit_price,
            strategy_version=EnsembleStrategy.version, rationale=f"{signal.rationale}; risk={risk.reason}",
            data_sha256=bars_digest(bars), status="proposed" if risk.allowed else "blocked",
        )
        store.save_decision(decision)
        note = memory.write_decision(decision)
        latency = int((time.monotonic() - before) * 1000)
        store.save_cycle(started, settings.provider, len(bars), latency, "ok", str(note))
        log.info("decision=%s action=%s status=%s price=%.2f", decision.decision_id, decision.action, decision.status, decision.reference_price)
        return decision.to_dict()
    except Exception as exc:
        latency = int((time.monotonic() - before) * 1000)
        store.save_cycle(started, settings.provider, 0, latency, "error", f"{type(exc).__name__}: {exc}")
        log.exception("cycle failed")
        raise


async def scheduler() -> None:
    consecutive_failures = 0
    for iteration in range(1, settings.max_cycles + 1):
        outcome = "ok"
        try:
            await run_cycle()
            consecutive_failures = 0
        except Exception as exc:
            outcome = f"error:{type(exc).__name__}"
            consecutive_failures += 1
        progress = {"iteration": iteration, "max_iterations": settings.max_cycles, "outcome": outcome, "updated_at": utc_now()}
        fd, tmp = tempfile.mkstemp(prefix="progress-", dir=settings.progress_file.parent)
        with os.fdopen(fd, "w") as handle:
            json.dump(progress, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, settings.progress_file)
        if consecutive_failures >= 2:
            log.error("scheduler stopped after two consecutive provider failures")
            break
        await asyncio.sleep(settings.cycle_seconds)


@app.on_event("startup")
async def startup() -> None:
    app.state.scheduler = asyncio.create_task(scheduler())


@app.on_event("shutdown")
async def shutdown() -> None:
    app.state.scheduler.cancel()


@app.get("/health")
def health() -> dict:
    return store.health()


@app.get("/decisions")
def decisions(limit: int = 20) -> list[dict]:
    return store.latest(max(1, min(limit, 100)))


@app.post("/cycles/run")
async def trigger_cycle() -> dict:
    return await run_cycle()
