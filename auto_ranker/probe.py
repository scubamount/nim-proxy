#!/usr/bin/env python3
"""NIM tier auto-ranker: probe candidate models, gate on structured-JSON fidelity,
rank survivors by latency, and hot-reload the proxy's alias routing (no restart).

Design (see AUTO_RANKER_SPEC.md):
- Fidelity gate rejects models that a naive speed-rank would wrongly pick:
  markdown-fence emitters that ignore response_format, and *-reasoning models
  whose `content` is empty (output goes to `reasoning_content`).
- Winner per alias -> rewrite the alias's `upstream` in the proxy overrides JSON.
  The proxy reads that file fresh on every request, so the change hot-reloads.
- Atomic write (temp file + os.replace). Aliases are additive: existing model
  entries in the overrides JSON are never removed or renamed.
- If NO model passes the gate, the last-good alias is left in place (never blanked)
  and a CRITICAL line is logged.

Pure stdlib except the probe HTTP call, which uses urllib. No PYTHONPATH deps.
Run with a clean env:  env -u PYTHONPATH python3.12 -m auto_ranker.probe
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# --- prompts per op-class -------------------------------------------------

# retain: short facts-list extraction. consolidation: nested schema with an
# observation_id that must be echoed back. Both demand response_format json_object.
_RETAIN_MESSAGES = [
    {
        "role": "system",
        "content": (
            "Extract atomic facts from the user text. Respond with ONLY a JSON "
            'object of the form {"facts": ["fact1", "fact2"]}. No prose, no markdown.'
        ),
    },
    {"role": "user", "content": "Andrew dives in Monterey and prefers a 7mm wetsuit."},
]

_CONSOLIDATION_MESSAGES = [
    {
        "role": "system",
        "content": (
            "Consolidate the observation. Respond with ONLY a JSON object of the form "
            '{"observation_id": "<echo the id>", "facts": ["fact1"]}. '
            "No prose, no markdown."
        ),
    },
    {
        "role": "user",
        "content": json.dumps(
            {"observation_id": "obs-4271", "text": "Andrew logged a 30m dive."}
        ),
    },
]

_PROMPTS = {"retain": _RETAIN_MESSAGES, "consolidation": _CONSOLIDATION_MESSAGES}


# --- fidelity gate (the load-bearing logic; unit-tested offline) ----------


def parse_content(response: dict) -> Optional[str]:
    """Pull choices[0].message.content out of an OpenAI-style response dict.

    Returns None if the path is missing. A *-reasoning model puts its output in
    `reasoning_content` and leaves `content` empty/None -> this returns "" or None,
    which check_fidelity treats as a gate failure.
    """
    try:
        msg = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return None
    return msg.get("content")


def _strip_fences(text: str) -> str:
    """Tolerate a single leading/trailing ```json fence. We do NOT try to rescue
    models that emit prose around JSON — those fail the gate on purpose. This only
    unwraps the one benign case where the whole body is a fenced JSON block.
    """
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def check_fidelity(response: dict, op_class: str) -> tuple[bool, str]:
    """Return (passed, reason). A model PASSES only if:
      1. non-empty content
      2. content parses as JSON
      3. parsed JSON has the expected shape (a `facts` list)
      4. consolidation variant echoes a nested `observation_id`
    """
    content = parse_content(response)
    if not content or not content.strip():
        return False, "empty content (reasoning-only or no output)"

    stripped = _strip_fences(content)
    # A model that emitted a markdown fence around otherwise-valid JSON is a soft
    # fail signal, but ponytail: we only hard-fail when JSON itself is unparseable.
    # The fence-strip above handles the whole-body-fenced case; anything with prose
    # outside the fence will fail json.loads below.
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return False, "content is not valid JSON (markdown/prose leak)"

    if isinstance(parsed, list):
        # Bare array is acceptable as a facts list.
        facts = parsed
    elif isinstance(parsed, dict):
        facts = parsed.get("facts")
    else:
        return False, "JSON is neither object nor array"

    if not isinstance(facts, list) or not facts:
        return False, "missing/empty `facts` list"

    if op_class == "consolidation":
        if not isinstance(parsed, dict) or not parsed.get("observation_id"):
            return False, "consolidation: missing echoed `observation_id`"

    return True, "ok"


# --- probing (network) ----------------------------------------------------


def _post(base: str, body: dict, timeout: float) -> dict:
    url = base.rstrip("/") + "/chat/completions"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer x"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def probe_model(
    base: str, model: str, op_class: str, samples: int, timeout: float
) -> dict:
    """Probe one model `samples` times. First call gates fidelity; all successful
    calls contribute a latency sample. Returns a result record.
    """
    messages = _PROMPTS[op_class]
    latencies: list[float] = []
    passed = False
    reason = "no successful call"
    for i in range(samples):
        body = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": 4096,  # ponytail: reasoning models burn budget before JSON; 512 starved gpt-oss (empty content, finish=length). Raise if a model needs more headroom.
            "temperature": 0,
            "stream": False,
        }
        t0 = time.monotonic()
        try:
            resp = _post(base, body, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            reason = f"request failed: {e}"
            # A model that fails/times out once is down — don't burn more samples on it.
            break
        dt = (time.monotonic() - t0) * 1000.0
        latencies.append(dt)
        if i == 0:
            passed, reason = check_fidelity(resp, op_class)
            if not passed:
                # Fidelity failure is terminal for this model — stop burning calls.
                break
    p50 = _p50(latencies) if latencies else None
    return {
        "model": model,
        "op_class": op_class,
        "passed": passed,
        "reason": reason,
        "latency_ms_p50": p50,
        "samples": len(latencies),
    }


def _p50(latencies: list[float]) -> float:
    """Median, dropping the single worst outlier when we have >=3 samples."""
    if len(latencies) >= 3:
        latencies = sorted(latencies)[:-1]
    return round(statistics.median(latencies), 1)


def rank(results: list[dict]) -> list[dict]:
    """PASS models sorted by p50 latency ascending. Fails dropped."""
    survivors = [r for r in results if r["passed"] and r["latency_ms_p50"] is not None]
    return sorted(survivors, key=lambda r: r["latency_ms_p50"])


# --- routing update (restart-free, atomic) --------------------------------


def load_overrides(path: Path) -> dict:
    if path.is_file():
        with path.open() as f:
            return json.load(f)
    return {}


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)  # atomic on POSIX


def apply_winners(
    overrides: dict, winners: dict[str, Optional[str]]
) -> tuple[dict, dict]:
    """Set each alias entry's `upstream` to its winner. Additive: never removes
    existing entries. If winner is None (nobody passed), the alias is left as-is
    (last-good preserved). Returns (new_overrides, changes) where changes maps
    alias -> (old_upstream, new_upstream) for entries that actually changed.
    """
    new = dict(overrides)
    changes: dict[str, tuple[Optional[str], str]] = {}
    for alias, winner in winners.items():
        if winner is None:
            continue  # keep last-good; never blank
        entry = dict(new.get(alias) or {})
        old = entry.get("upstream")
        if old != winner:
            entry["upstream"] = winner
            new[alias] = entry
            changes[alias] = (old, winner)
        else:
            new[alias] = entry  # unchanged but ensure present
    return new, changes


# --- audit log ------------------------------------------------------------


def append_audit(log_path: Path, record: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")


# --- orchestration --------------------------------------------------------


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p))


def run(config: dict, dry_run: bool = False) -> dict:
    base = config["proxy_base"]
    samples = int(config.get("probe_samples", 3))
    timeout = float(config.get("probe_timeout_s", 30))
    overrides_path = _expand(config["overrides_path"])
    audit_path = _expand(config["audit_log"])

    # Live catalog: only probe candidates the proxy actually serves right now.
    available = _live_models(base, timeout)

    all_results: list[dict] = []
    winners: dict[str, Optional[str]] = {}
    per_alias_ranked: dict[str, list[dict]] = {}

    for alias, candidates in config["aliases"].items():
        op_class = config["op_class"].get(alias, "retain")
        eligible = [m for m in candidates if not available or m in available]
        results = [
            probe_model(base, m, op_class, samples, timeout) for m in eligible
        ]
        all_results.extend(results)
        ranked = rank(results)
        per_alias_ranked[alias] = ranked
        winners[alias] = ranked[0]["model"] if ranked else None

    overrides = load_overrides(overrides_path)
    new_overrides, changes = apply_winners(overrides, winners)

    routing_changed = bool(changes)
    if routing_changed and not dry_run:
        atomic_write_json(overrides_path, new_overrides)

    ts = datetime.now(timezone.utc).isoformat()
    critical = [a for a, w in winners.items() if w is None]
    record = {
        "ts": ts,
        "results": all_results,
        "winners": {
            a: (r[0]["model"] if r else None) for a, r in per_alias_ranked.items()
        },
        "fallbacks": {
            a: (r[1]["model"] if len(r) > 1 else None)
            for a, r in per_alias_ranked.items()
        },
        "routing_changed": routing_changed,
        "changes": {a: {"from": o, "to": n} for a, (o, n) in changes.items()},
        "critical_no_pass": critical,
        "dry_run": dry_run,
    }
    if not dry_run:
        append_audit(audit_path, record)

    for alias in critical:
        print(
            f"[nim-ranker] CRITICAL: no model passed the gate for {alias}; "
            f"leaving last-good alias in place (not blanking).",
            file=sys.stderr,
            flush=True,
        )

    return record


def _live_models(base: str, timeout: float) -> set[str]:
    url = base.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(
            url, headers={"Authorization": "Bearer x"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        return {m["id"] for m in data.get("data", [])}
    except Exception as e:  # noqa: BLE001 - catalog is best-effort; empty => probe all
        print(f"[nim-ranker] catalog fetch failed ({e}); probing full allowlist.",
              file=sys.stderr, flush=True)
        return set()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="NIM tier auto-ranker")
    ap.add_argument(
        "--config",
        default=str(Path(__file__).parent / "candidates.json"),
        help="path to candidates.json",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="probe + rank + log to stdout, but do NOT write overrides or audit log",
    )
    args = ap.parse_args(argv)

    with open(args.config) as f:
        config = json.load(f)

    record = run(config, dry_run=args.dry_run)
    print(json.dumps(record, indent=2))
    # Non-zero exit if any alias has no passing model (surfaces in launchd log).
    return 1 if record["critical_no_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
