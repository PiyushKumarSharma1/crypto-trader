from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
import re
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

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


@asynccontextmanager
async def lifespan(application: FastAPI):
    task = asyncio.create_task(scheduler())
    application.state.scheduler = task
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Nova Market Control", version="0.1.0", lifespan=lifespan)


class WalletConnection(BaseModel):
    address: str
    chain_id: str

    @field_validator("address")
    @classmethod
    def valid_address(cls, value: str) -> str:
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
            raise ValueError("invalid EVM address")
        return value.lower()

    @field_validator("chain_id")
    @classmethod
    def valid_chain(cls, value: str) -> str:
        if not re.fullmatch(r"0x[0-9a-fA-F]+", value):
            raise ValueError("invalid hexadecimal chain id")
        return value.lower()


WALLET_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'none'">
<title>Nova · MetaMask</title><style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#080b12;color:#eef2ff}
.card{width:min(560px,calc(100vw - 48px));padding:34px;border:1px solid #29344c;border-radius:24px;background:linear-gradient(145deg,#131a28,#0b101a);box-shadow:0 30px 90px #000a}
.eyebrow{color:#7dd3fc;letter-spacing:.16em;text-transform:uppercase;font-size:12px}.status{margin:24px 0;padding:18px;border-radius:14px;background:#070a10;border:1px solid #202a3e;word-break:break-all}
button{border:0;border-radius:12px;padding:13px 18px;font-weight:750;cursor:pointer;background:#f6851b;color:#111827}button.secondary{margin-left:8px;background:#263148;color:#eef2ff}button:disabled{opacity:.55;cursor:wait}
.note{margin-top:20px;color:#9aa7bd;font-size:13px;line-height:1.55}.ok{color:#86efac}.error{color:#fca5a5}
</style></head><body><main class="card"><div class="eyebrow">Nova wallet gateway</div><h1>Connect MetaMask</h1>
<div id="status" class="status">Ready for your approval.</div><button id="connect">Connect MetaMask</button><button id="disconnect" class="secondary">Disconnect locally</button>
<div class="note">The connection records only your public address and chain ID. Nova does not request a recovery phrase, private key, message signature, token approval, or transaction.</div></main>
<script>
let provider=null; const status=document.querySelector('#status'), connect=document.querySelector('#connect');
function show(message,kind=''){status.className='status '+kind;status.textContent=message}
window.addEventListener('eip6963:announceProvider',event=>{const d=event.detail;if(!provider&&(d.info?.rdns==='io.metamask'||d.provider?.isMetaMask))provider=d.provider});
window.dispatchEvent(new Event('eip6963:requestProvider'));
setTimeout(()=>{if(!provider&&window.ethereum?.isMetaMask)provider=window.ethereum;if(!provider)show('MetaMask extension was not detected. Install or enable it, then reload.','error')},400);
async function sync(address,chainId){const r=await fetch('/api/wallet/connect',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({address,chain_id:chainId})});if(!r.ok)throw new Error('Nova rejected wallet metadata');const data=await r.json();show(`Connected ${data.address} on chain ${data.chain_id}`,'ok')}
connect.addEventListener('click',async()=>{connect.disabled=true;try{if(!provider)throw new Error('MetaMask extension not detected');const accounts=await provider.request({method:'eth_requestAccounts'});const chainId=await provider.request({method:'eth_chainId'});if(!accounts.length)throw new Error('No account selected');await sync(accounts[0],chainId)}catch(e){show(e?.code===4001?'Connection request rejected in MetaMask.':(e.message||String(e)),'error')}finally{connect.disabled=false}});
document.querySelector('#disconnect').addEventListener('click',async()=>{await fetch('/api/wallet/disconnect',{method:'POST'});show('Disconnected from Nova locally.')});
function bind(){if(!provider)return;provider.on?.('accountsChanged',a=>a.length?provider.request({method:'eth_chainId'}).then(c=>sync(a[0],c)):show('MetaMask account access removed.'));provider.on?.('chainChanged',c=>provider.request({method:'eth_accounts'}).then(a=>a.length&&sync(a[0],c)))}
setTimeout(bind,500);
</script></body></html>"""


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


@app.get("/health")
def health() -> dict:
    return store.health()


@app.get("/decisions")
def decisions(limit: int = 20) -> list[dict]:
    return store.latest(max(1, min(limit, 100)))


@app.get("/wallet", response_class=HTMLResponse)
def wallet_page() -> str:
    return WALLET_PAGE


@app.get("/api/wallet")
def wallet_status() -> dict:
    return store.wallet()


@app.post("/api/wallet/connect")
def wallet_connect(connection: WalletConnection) -> dict:
    return store.connect_wallet(connection.address, connection.chain_id, utc_now())


@app.post("/api/wallet/disconnect")
def wallet_disconnect() -> dict:
    return store.disconnect_wallet()


@app.post("/cycles/run")
async def trigger_cycle() -> dict:
    return await run_cycle()
