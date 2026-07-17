"""Fidelity-gate + routing-update tests for the NIM auto-ranker.

Run: env -u PYTHONPATH .venv/bin/python -m pytest tests/test_probe.py -q
(or plain `python -m pytest`). No network — everything here is offline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_ranker import probe  # noqa: E402


# --- fidelity gate --------------------------------------------------------

def _resp(content, reasoning=None):
    msg = {"content": content}
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    return {"choices": [{"message": msg}]}


def test_reasoning_model_rejected():
    # *-reasoning: content empty, output in reasoning_content -> MUST fail.
    r = _resp("", reasoning='{"facts": ["x"]}')
    passed, reason = probe.check_fidelity(r, "retain")
    assert not passed and "empty content" in reason


def test_none_content_rejected():
    passed, _ = probe.check_fidelity(_resp(None), "retain")
    assert not passed


def test_valid_json_object_passes():
    passed, reason = probe.check_fidelity(_resp('{"facts": ["Andrew dives"]}'), "retain")
    assert passed and reason == "ok"


def test_valid_json_array_passes():
    passed, _ = probe.check_fidelity(_resp('["fact one", "fact two"]'), "retain")
    assert passed


def test_prose_leak_rejected():
    # mistral-small-4 style: ignores response_format, wraps prose around JSON.
    passed, reason = probe.check_fidelity(
        _resp('Sure! Here you go: {"facts": ["x"]} hope that helps'), "retain"
    )
    assert not passed and "not valid JSON" in reason


def test_whole_body_fenced_json_tolerated():
    passed, _ = probe.check_fidelity(_resp('```json\n{"facts": ["x"]}\n```'), "retain")
    assert passed


def test_empty_facts_rejected():
    passed, reason = probe.check_fidelity(_resp('{"facts": []}'), "retain")
    assert not passed and "facts" in reason


def test_consolidation_requires_observation_id():
    ok = _resp('{"observation_id": "obs-1", "facts": ["x"]}')
    miss = _resp('{"facts": ["x"]}')
    assert probe.check_fidelity(ok, "consolidation")[0]
    assert not probe.check_fidelity(miss, "consolidation")[0]


# --- routing update -------------------------------------------------------

def test_apply_winners_changes_and_additive():
    overrides = {
        "existing/model": {"temperature": 1},  # must survive untouched
        "auto/retain": {"upstream": "old-model"},
    }
    winners = {"auto/retain": "new-model", "auto/reflect": "reflect-model"}
    new, changes = probe.apply_winners(overrides, winners)
    assert new["existing/model"] == {"temperature": 1}            # additive
    assert new["auto/retain"]["upstream"] == "new-model"          # changed
    assert new["auto/reflect"]["upstream"] == "reflect-model"     # created
    assert changes["auto/retain"] == ("old-model", "new-model")
    assert "auto/reflect" in changes


def test_no_winner_preserves_last_good():
    # Nobody passed the gate for auto/retain -> winner None -> keep existing, NOT blank.
    overrides = {"auto/retain": {"upstream": "known-good"}}
    new, changes = probe.apply_winners(overrides, {"auto/retain": None})
    assert new["auto/retain"]["upstream"] == "known-good"
    assert changes == {}


def test_no_change_when_winner_matches():
    overrides = {"auto/retain": {"upstream": "same"}}
    _, changes = probe.apply_winners(overrides, {"auto/retain": "same"})
    assert changes == {}


def test_atomic_write_roundtrip(tmp_path):
    p = tmp_path / "sub" / "overrides.json"
    probe.atomic_write_json(p, {"auto/retain": {"upstream": "m"}})
    assert json.loads(p.read_text())["auto/retain"]["upstream"] == "m"
    assert not p.with_suffix(".json.tmp").exists()  # temp cleaned up


def test_rank_drops_fails_and_sorts_by_latency():
    results = [
        {"model": "slow", "passed": True, "latency_ms_p50": 900},
        {"model": "fast", "passed": True, "latency_ms_p50": 200},
        {"model": "broken", "passed": False, "latency_ms_p50": 50},
        {"model": "nocall", "passed": True, "latency_ms_p50": None},
    ]
    ranked = probe.rank(results)
    assert [r["model"] for r in ranked] == ["fast", "slow"]


def _run_without_pytest() -> int:
    """Stdlib fallback so tests run with zero deps. tmp_path -> a real temp dir."""
    import inspect
    import tempfile
    g = dict(globals())
    tests = sorted(k for k, v in g.items() if k.startswith("test_") and callable(v))
    failed = 0
    for name in tests:
        fn = g[name]
        try:
            if "tmp_path" in inspect.signature(fn).parameters:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        import pytest  # noqa: F401
        raise SystemExit(__import__("pytest").main([__file__, "-q"]))
    except ImportError:
        raise SystemExit(_run_without_pytest())
