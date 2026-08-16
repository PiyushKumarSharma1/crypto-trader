# Nova Market Control

Nova is a real-market ingestion, strategy, risk, audit, and MCP memory control plane. It consumes live public exchange data and produces immutable, reviewable order intents. It does not possess wallet keys, seed phrases, exchange secrets, or an unattended order-submission path.

## Run

```bash
cd /Users/piyushkumarsharma/Documents/Codex/2026-08-16/u/crypto_trading_agent
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
./run_trading_system.sh
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/cycles/run
curl http://127.0.0.1:8765/decisions
```

Open `http://127.0.0.1:8765/wallet` in the browser profile containing MetaMask and click **Connect MetaMask**. MetaMask must receive the request from that explicit click; Nova records only the selected public EVM address and chain ID. The wallet gateway contains no signing, approval, or transaction method.

The scheduler runs immediately and then every 15 minutes for a bounded 96-cycle (24-hour) deployment. Each cycle atomically updates `runtime/progress.json`; a supervisor may launch the next bounded run after inspection. SQLite uses WAL mode at `runtime/nova.db`. Obsidian-compatible notes are atomically written under `runtime/vault/Decisions` with a SHA-256 digest of the input bars.

## MCP

Register the absolute command from `mcp.json`. Direct smoke test:

```bash
.venv/bin/python -m nova.mcp_server
```

The server uses stdio and therefore waits silently for its MCP host. It exposes `latest_decisions` and `system_health`; it exposes no transaction tool.

## Operations

- Health: `GET /health`
- Trigger one cycle: `POST /cycles/run`
- Inspect decisions: `GET /decisions`
- Emergency stop: run `./stop_trading_system.sh`. No orders are sent by this service.
- Change feed: set `NOVA_PROVIDER=hyperliquid` or `kraken`.
- Keep the API bound to loopback unless authentication and TLS are added.

## Acceptance and iteration limits

Acceptance requires: unit tests pass; a real provider cycle returns bars; SQLite records the cycle; a Markdown decision note exists; `/health` reports the result. Validation commands are `.venv/bin/pytest`, `.venv/bin/python -m compileall -q nova tests`, `curl http://127.0.0.1:8765/health`, and an MCP in-memory `system_health` call. The maximum unattended iteration count is 96 and progress persists in `runtime/progress.json`. The run stops after iteration 96 or when the same provider failure recurs without recovery. Strategy changes require walk-forward evaluation with point-in-time data and realistic fees. No candidate is promoted solely from in-sample Sharpe; promotion requires an independently held-out improvement, a drawdown non-regression, and a minimum observation count.

Market decisions and backtests are uncertain estimates, not guarantees of profitability.
