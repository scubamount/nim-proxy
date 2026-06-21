#!/usr/bin/env bash
# Secure launcher for nim-proxy.
# Sources NVIDIA_API_KEY from ~/.hermes/.env (0600, the secret source of truth)
# at startup, then execs uvicorn. The key never appears in the plist, in `ps`
# arguments, or in any committed file — only in the proxy process environment.
set -eu

PROXY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${NIM_PROXY_KEY_ENV_FILE:-$HOME/.hermes/.env}"
PY="${PY:-$PROXY_DIR/.venv/bin/python}"
HOST="${NIM_PROXY_HOST:-127.0.0.1}"
PORT="${NIM_PROXY_PORT:-8001}"

# Source the NVIDIA key from the locked-down env file (first match wins).
if [ -f "$ENV_FILE" ]; then
  key_line="$(grep -E '^NVIDIA_API_KEY=' "$ENV_FILE" | head -1 || true)"
  if [ -n "$key_line" ]; then
    val="${key_line#NVIDIA_API_KEY=}"
    # strip surrounding single/double quotes and trailing CR
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"; val="${val#\'}"
    val="${val%$'\r'}"
    export NVIDIA_API_KEY="$val"
    unset val key_line
  fi
fi

if [ -z "${NVIDIA_API_KEY:-}" ]; then
  echo "[launch-with-key] WARNING: NVIDIA_API_KEY not found in $ENV_FILE — proxy will 401 against NVIDIA." >&2
fi

cd "$PROXY_DIR"
exec "$PY" -u -m uvicorn nim_proxy:app --host "$HOST" --port "$PORT" --no-access-log
