# NIM tier auto-ranker — build spec (2026-07-17)

## Goal
Hourly job that probes candidate NIM models for hindsight's hot path, gates them on
**structured-JSON fidelity** (not just latency), ranks survivors by latency, and updates
the proxy's alias routing so hindsight always uses the best *currently-available* model —
with **zero daemon/proxy restarts** on routing change.

## Why this design
- Proxy `nim_proxy/config.py::load_overrides()` reads the `$NIM_PROXY_OVERRIDES` JSON file
  **fresh on every request** → updating the JSON is hot-reloaded, no restart.
- Proxy `nim_proxy/app.py::_apply_override()` already supports an `"upstream"` key that
  rewrites `body["model"]` → an alias `auto/retain` is just an override whose `upstream`
  points at the current best model. **No app.py code change needed.**
- Hindsight points at `auto/retain` / `auto/consolidation` / `auto/reflect` ONCE; its
  `hermes.env` never changes again.

## Fidelity gate (CRITICAL — latency alone picks broken models)
Verified-unusable models that a naive speed-rank would wrongly pick:
- `mistralai/mistral-small-4-119b-2603` — fastest (201ms) but IGNORES response_format,
  emits markdown fences + invents keys. UNUSABLE.
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (any `*-reasoning`) — output goes to
  `reasoning_content`, `content` is EMPTY. Hindsight reads `content` → nothing. UNUSABLE.

A model PASSES the gate only if, given a retain-style prompt with
`response_format={"type":"json_object"}`, the response has:
1. non-empty `choices[0].message.content`
2. `content` parses as JSON
3. the parsed JSON is an object/array with the expected shape (facts list)
4. (consolidation variant) can echo a nested `observation_id` field

## Candidate models
Query `GET http://127.0.0.1:8001/v1/models` for the live catalog, then probe a curated
allowlist (do NOT probe all ~100 — costs money + time). Start allowlist:
- openai/gpt-oss-20b            (known-good fallback, current primary)
- meta/llama-4-maverick-17b-128e-instruct   (known-good when up)
- nvidia/nemotron-3-* (NON-reasoning variants only)
- Any new fast instruct models Andrew adds to the allowlist file

Allowlist lives in a config file (`auto_ranker/candidates.json`) so Andrew edits it without
touching code.

## Ranking
Among PASS models, rank by measured p50 latency over N=3 probe calls (drop outliers).
Separate ranking per op-class if desired (retain=fast/short, consolidation=nested-schema).
Winner → alias upstream. Keep a 2nd-place as documented fallback (hindsight litellmrouter
still has its own fallback chain; alias only sets the primary).

## Routing update (restart-free)
1. One-time: set `NIM_PROXY_OVERRIDES=$HOME/.config/nim-proxy-overrides.json` in the plist,
   seed the JSON from current `overrides.py` MODEL_OVERRIDES, restart proxy ONCE.
2. Hourly: probe → rank → if winner changed, rewrite the `auto/*` entries' `upstream` in the
   JSON (atomic write: temp file + os.replace). Next proxy request hot-reloads it. No restart.
3. If NO model passes the gate (all NIM down): leave last-good alias in place, log CRITICAL,
   do NOT blank the alias (blanking would break hindsight entirely).

## Audit trail (SOC2/ISO27001)
Append each run to `~/.config/nim-proxy-ranker.log` (JSONL): timestamp, per-model
pass/fail + latency, chosen winner per alias, whether routing changed. Never delete.

## Schedule
launchd StartInterval=3600 (hourly), clean env (NO PYTHONPATH — see pitfall below),
own plist `com.scubamount.nim-ranker.plist`. Log to a file, KeepAlive=false, RunAtLoad=true.

## PITFALLS (learned 2026-07-17)
- **PYTHONPATH leak**: a hermes shell exports PYTHONPATH pointing at the py3.11 venv, which
  poisons python3.12 (loads py3.11 pydantic_core.so → ABI crash). The ranker MUST run with a
  clean env (launchd plist has no PYTHONPATH; if invoked manually, `env -u PYTHONPATH`).
- **Proxy serves multiple tools** (opencode, hermes). Aliases are additive — do not remove or
  rename existing model entries in the overrides JSON when seeding.
- **Single-line-JSON**: hindsight hermes.env is fragile; the ranker touches the PROXY json,
  not hermes.env, so this is avoided by design. Keep it that way.
- Repo is `scubamount/nim-proxy` — allowed remote. Commit + push OK.

## Deliverables
- `auto_ranker/probe.py` — fidelity+latency probe, ranking, atomic JSON update
- `auto_ranker/candidates.json` — editable allowlist
- `scripts/com.scubamount.nim-ranker.plist` — hourly launchd job
- `scripts/install-ranker.sh` — installs plist, sets NIM_PROXY_OVERRIDES in proxy plist,
  seeds overrides JSON, restarts proxy once
- `tests/test_probe.py` — unit tests for the fidelity gate (mock a reasoning-model response
  with empty content → must FAIL gate; mock valid JSON → must PASS)
- README section documenting `auto/*` aliases + how hindsight points at them
