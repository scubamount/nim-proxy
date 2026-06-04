#!/usr/bin/env bash
set -e

PROXY_DIR=${PROXY_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
PORT=${NIM_PROXY_PORT:-8001}
LOG=${NIM_PROXY_LOG:-/tmp/nim_proxy.log}
PY=${PY:-/opt/homebrew/bin/python3.12}

PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    kill -9 $PIDS 2>/dev/null || true
fi

find "$PROXY_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROXY_DIR" -name "*.pyc" -delete 2>/dev/null || true

cd "$PROXY_DIR"
nohup "$PY" -u -m uvicorn nim_proxy:app --host 127.0.0.1 --port "$PORT" --no-access-log > "$LOG" 2>&1 &
PID=$!
disown "$PID"

for i in $(seq 1 10); do
    if lsof -ti:"$PORT" >/dev/null 2>&1; then
        echo "nim-proxy up: pid=$PID port=$PORT log=$LOG"
        exit 0
    fi
    sleep 0.3
done

echo "nim-proxy failed to start" >&2
tail -20 "$LOG" >&2
exit 1
