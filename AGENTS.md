## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when graphify query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

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

