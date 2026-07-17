#!/usr/bin/env bash
# One-time installer for the NIM tier auto-ranker.
# Idempotent. Does the side-effecting steps the ranker itself must NOT do:
#   1. Seed the proxy overrides JSON from the built-in overrides.py (if absent).
#   2. Add NIM_PROXY_OVERRIDES to the proxy launchd plist (if not already set).
#   3. Restart the proxy ONCE so it reads the JSON file.
#   4. Install + load the hourly ranker launchd job.
#
# Run:  ./scripts/install-ranker.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
OVERRIDES_JSON="$HOME/.config/nim-proxy-overrides.json"
PROXY_PLIST="$HOME/Library/LaunchAgents/com.scubamount.nim-proxy.plist"
RANKER_PLIST_SRC="$REPO/scripts/com.scubamount.nim-ranker.plist"
RANKER_PLIST_DST="$HOME/Library/LaunchAgents/com.scubamount.nim-ranker.plist"

echo "==> 1. Seed overrides JSON"
if [ -f "$OVERRIDES_JSON" ]; then
  echo "    exists, leaving as-is: $OVERRIDES_JSON"
else
  mkdir -p "$(dirname "$OVERRIDES_JSON")"
  # Dump the built-in dict to JSON so nothing the proxy already serves is lost.
  env -u PYTHONPATH "$PY" - "$OVERRIDES_JSON" <<'PYEOF'
import json, sys
from nim_proxy import overrides
json.dump(dict(overrides.MODEL_OVERRIDES), open(sys.argv[1], "w"), indent=2)
print("    seeded from overrides.py ->", sys.argv[1])
PYEOF
fi

echo "==> 2. Ensure NIM_PROXY_OVERRIDES in proxy plist"
if [ ! -f "$PROXY_PLIST" ]; then
  echo "    ERROR: proxy plist not found: $PROXY_PLIST" >&2; exit 1
fi
if /usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:NIM_PROXY_OVERRIDES" "$PROXY_PLIST" >/dev/null 2>&1; then
  echo "    already set, skipping"
  PROXY_CHANGED=0
else
  /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:NIM_PROXY_OVERRIDES string $OVERRIDES_JSON" "$PROXY_PLIST"
  echo "    added NIM_PROXY_OVERRIDES=$OVERRIDES_JSON"
  PROXY_CHANGED=1
fi

echo "==> 3. Restart proxy (only if plist changed)"
if [ "${PROXY_CHANGED:-0}" = "1" ]; then
  launchctl unload "$PROXY_PLIST" 2>/dev/null || true
  launchctl load "$PROXY_PLIST"
  sleep 2
  if curl -sS -m 3 http://127.0.0.1:8001/v1/models -H "Authorization: Bearer x" | head -c 20 | grep -q '{'; then
    echo "    proxy up after restart"
  else
    echo "    WARNING: proxy not responding after restart; check /tmp/nim_proxy.log" >&2
  fi
else
  echo "    no proxy plist change; not restarting (per AGENTS.md policy)"
fi

echo "==> 4. Install hourly ranker job"
cp "$RANKER_PLIST_SRC" "$RANKER_PLIST_DST"
launchctl unload "$RANKER_PLIST_DST" 2>/dev/null || true
launchctl load "$RANKER_PLIST_DST"
echo "    loaded com.scubamount.nim-ranker (hourly)"

echo
echo "Done. First run fires at load (RunAtLoad) + every 3600s. Logs: /tmp/nim_ranker.log"
echo "Dry-run manually:  cd $REPO && env -u PYTHONPATH $PY -m auto_ranker.probe --dry-run"
echo
echo "NEXT (manual, when ready to cut hindsight over):"
echo "  point hermes.env LITELLMROUTER models at auto/retain, auto/consolidation, auto/reflect"
echo "  then restart the hindsight daemon once."
