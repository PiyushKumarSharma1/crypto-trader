#!/bin/sh
set -eu
PORT="${NOVA_BIND_PORT:-8765}"
PIDS="$(lsof -ti "tcp:$PORT" 2>/dev/null || true)"
if [ -z "$PIDS" ]; then
  echo "Nova service is not listening on port $PORT"
  exit 0
fi
for pid in $PIDS; do
  kill "$pid"
done
echo "Stopped Nova service PID(s): $PIDS"
