from __future__ import annotations

from mcp.server import MCPServer

from .config import Settings
from .store import Store

mcp = MCPServer("nova-market-memory")
settings = Settings()
settings.prepare()
store = Store(settings.database)


@mcp.tool()
def latest_decisions(limit: int = 10) -> list[dict]:
    """Return recent market decisions with rationale and evidence digests."""
    return store.latest(max(1, min(limit, 50)))


@mcp.tool()
def system_health() -> dict:
    """Return the latest ingestion cycle and decision count."""
    return store.health()


if __name__ == "__main__":
    mcp.run()
