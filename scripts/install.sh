#!/usr/bin/env bash
set -e

PROXY_DIR=${PROXY_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
VENV="$PROXY_DIR/.venv"
PORT=${NIM_PROXY_PORT:-8001}
LOG=${NIM_PROXY_LOG:-/tmp/nim_proxy.log}
PY=${PY:-/opt/homebrew/bin/python3.12}
PLIST="$HOME/Library/LaunchAgents/com.scubamount.nim-proxy.plist"

if ! command -v git >/dev/null 2>&1; then
    echo "WARNING: git not found" >&2
fi
if ! command -v python3.12 >/dev/null 2>&1; then
    echo "WARNING: python3.12 not found" >&2
fi
if [ -z "${NVIDIA_API_KEY:-}" ]; then
    echo "WARNING: NVIDIA_API_KEY is not set. The proxy may fail to start." >&2
fi

if [ ! -d "$VENV" ]; then
    "$PY" -m venv "$VENV"
fi

"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install -e "$PROXY_DIR"

VENV_PY="$VENV/bin/python"
"$PROXY_DIR/scripts/autolaunch.sh" install

echo ""
echo "Install complete."
echo "  venv:  $VENV"
echo "  port:  $PORT"
echo "  log:   $LOG"
echo "  plist: $PLIST"
echo ""
if ! grep -q 'NVIDIA_API_KEY' "$HOME/.zshrc" 2>/dev/null; then
    echo "Add to ~/.zshrc:"
    echo "  export NVIDIA_API_KEY='your-key-here'"
fi
