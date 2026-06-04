#!/usr/bin/env bash
set -e

PROXY_DIR=${PROXY_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
VENV="$PROXY_DIR/.venv"
PY=${PY:-/opt/homebrew/bin/python3.12}

if [ -d "$PROXY_DIR/.git" ]; then
    cd "$PROXY_DIR"
    git pull
else
    echo "WARNING: $PROXY_DIR is not a git repo, skipping pull" >&2
fi

if [ ! -d "$VENV" ]; then
    "$PY" -m venv "$VENV"
    "$VENV/bin/pip" install -U pip
fi

"$VENV/bin/pip" install -e "$PROXY_DIR"

"$PROXY_DIR/scripts/restart.sh"
