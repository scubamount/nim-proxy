## Proxy restart policy

The proxy at `127.0.0.1:8001` is managed by launchd (`~/Library/LaunchAgents/com.scubamount.nim-proxy.plist`) and serves multiple chat tools (opencode, hermes, anything else). **Do not restart it unless absolutely required.**

Restart is required only when:
- `nim_proxy/overrides.py` is edited (Python module reload needed for new model dict entries)
- `nim_proxy/app.py` or `nim_proxy/config.py` are edited (code changes)
- A package dependency changes
- The process is actually dead and not listening

Restart is **NOT** required for:
- Changes to `examples/*.json` (only loaded when `NIM_PROXY_OVERRIDES` is set)
- Changes to `README.md`, `pyproject.toml`, `scripts/*.sh`, `tests/*`
- Testing the proxy with curl (just hit it; launchd keeps it alive)
- Graph updates
- Git commits, pushes, or pulls

When restart is unavoidable, use `./scripts/restart.sh` once and do not retry. If `lsof -ti:8001` shows multiple PIDs after restart, do NOT keep killing — let launchd resolve it (KeepAlive=true will respawn the right one).

To verify the proxy is up: `curl -sS -m 3 http://127.0.0.1:8001/v1/models -H "Authorization: Bearer x" | head -c 100` should return a JSON list.


## Auto-ranker (auto/* aliases)

`auto/retain|consolidation|reflect` upstreams are managed by the hourly ranker
(`auto_ranker/probe.py`). Do NOT hand-edit their `upstream` in the overrides JSON —
the next run overwrites it. To change candidates, edit `auto_ranker/candidates.json`.
See README "Auto-ranker" section. Audit: `~/.config/nim-proxy-ranker.log`.
