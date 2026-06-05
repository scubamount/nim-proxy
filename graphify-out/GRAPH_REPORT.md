# Graph Report - scubamount-nim-proxy  (2026-06-04)

## Corpus Check
- 15 files · ~1,830 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 78 nodes · 82 edges · 18 communities (8 shown, 10 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7d62f0a2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]

## God Nodes (most connected - your core abstractions)
1. `scubamount-nim-proxy` - 11 edges
2. `nvidia/nemotron-3-ultra-550b-a55b` - 8 edges
3. `_capture_post()` - 7 edges
4. `load_overrides()` - 6 edges
5. `catch_all()` - 5 edges
6. `stepfun-ai/step-3.7-flash` - 4 edges
7. `_apply_override()` - 4 edges
8. `test_max_tokens_incoming_wins()` - 4 edges
9. `extra_body` - 3 edges
10. `autolaunch.sh script` - 3 edges

## Surprising Connections (you probably didn't know these)
- `_apply_override()` --calls--> `load_overrides()`  [EXTRACTED]
  nim_proxy/app.py → nim_proxy/config.py

## Import Cycles
- None detected.

## Communities (18 total, 10 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.18
Nodes (12): _capture_post(), When incoming max_tokens > override, incoming value used., Return a mock for httpx.AsyncClient.post that records calls., Nemotron model gets temperature=1, top_p=0.95, max_tokens=16384, reasoning field, Unknown model passes through without extra fields., Upstream URL preserves /v1 (no double /v1/v1)., When incoming max_tokens < override, override value used., test_default_override_applied() (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.26
Nodes (8): _apply_override(), main(), FastAPI app: OpenAI-compatible request handler that injects per-model overrides., load_overrides(), Centralized config from env vars. Pure stdlib., Return override dict. JSON file at $NIM_PROXY_OVERRIDES if set, else built-in., scubamount-nim-proxy: OpenAI-compatible bridge to NVIDIA NIM with per-model over, Tests for per-model override injection.

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (12): enable_thinking, chat_template_kwargs, reasoning_budget, nvidia/nemotron-3-ultra-550b-a55b, extra_body, max_tokens, temperature, top_p (+4 more)

### Community 3 - "Community 3"
Cohesion: 0.50
Nodes (4): catch_all(), Request, str, StreamingResponse

### Community 4 - "Community 4"
Cohesion: 0.83
Nodes (3): install_plist(), uninstall_plist(), autolaunch.sh script

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (12): Auth, Configure overrides, Install, License, Opencode, Override schema, Project layout, Run (+4 more)

## Knowledge Gaps
- **27 isolated node(s):** `plugin`, `temperature`, `top_p`, `max_tokens`, `enable_thinking` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `catch_all()` connect `Community 3` to `Community 1`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **What connects `plugin`, `temperature`, `top_p` to the rest of the system?**
  _38 weakly-connected nodes found - possible documentation gaps or missing edges._