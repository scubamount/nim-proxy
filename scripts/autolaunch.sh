#!/usr/bin/env bash
set -e

PROXY_DIR=${PROXY_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
PORT=${NIM_PROXY_PORT:-8001}
LOG=${NIM_PROXY_LOG:-/tmp/nim_proxy.log}
VENV="$PROXY_DIR/.venv"
VENV_PY="$VENV/bin/python"
PLIST="$HOME/Library/LaunchAgents/com.scubamount.nim-proxy.plist"
PLIST_SRC="$PROXY_DIR/scripts/com.scubamount.nim-proxy.plist"

install_plist() {
    mkdir -p "$(dirname "$PLIST")"
    sed -e "s|__PROXY_DIR__|$PROXY_DIR|g" \
        -e "s|__VENV_PY__|$VENV_PY|g" \
        -e "s|__LOG__|$LOG|g" \
        -e "s|__PORT__|$PORT|g" \
        "$PLIST_SRC" > "$PLIST"
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "nim-proxy launchd plist installed: $PLIST"
}

uninstall_plist() {
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "nim-proxy launchd plist removed: $PLIST"
}

case "${1:-}" in
    install)
        install_plist
        ;;
    uninstall)
        uninstall_plist
        ;;
    *)
        echo "Usage: $0 {install|uninstall}" >&2
        exit 1
        ;;
esac
