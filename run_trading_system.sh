#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p runtime
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
PYTHON="${NOVA_PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "Missing .venv; run: /opt/homebrew/bin/python3.11 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 2
fi
exec "$PYTHON" -m uvicorn nova.service:app --host "${NOVA_BIND_HOST:-127.0.0.1}" --port "${NOVA_BIND_PORT:-8765}"
