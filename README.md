# scubamount-nim-proxy

Local proxy that sits between your OpenAI-compatible clients and NVIDIA's NIM API. It rewrites per-model parameters (temperature, top_p, max_tokens, reasoning settings) so each model gets tuned defaults without touching client config. Drop-in. One process. No cloud dependency.

## Install

```bash
git clone https://github.com/scubamount/nim-proxy ~/code/scubamount-nim-proxy
cd ~/code/scubamount-nim-proxy
./scripts/install.sh
```

## Auth

Set your NVIDIA API key in your shell profile:

```bash
export NVIDIA_API_KEY=nvapi-...
```

Add that line to `~/.zshrc` (or `~/.bashrc`). The proxy forwards it upstream.

## Run

```bash
./scripts/restart.sh
```

Runs at `http://127.0.0.1:8001`. The install script also sets up a login autolaunch so it starts on boot.

## Configure overrides

Two ways:

1. Edit `nim_proxy/overrides.py` directly (Python dict).
2. Set `NIM_PROXY_OVERRIDES` to point at a JSON file:

```bash
export NIM_PROXY_OVERRIDES=$HOME/.config/nim-proxy-overrides.json
```

Same shape either way. See `examples/overrides.json` for the full schema.

### Override schema

| Field          | Type      | Description                              |
|----------------|-----------|------------------------------------------|
| `model`        | `string`  | NIM model ID (e.g. `nvidia/nemotron-3-ultra-550b-a55b`) |
| `temperature`  | `float`   | Sampling temperature                     |
| `top_p`        | `float`   | Nucleus sampling cutoff                  |
| `max_tokens`   | `int`     | Max response tokens                      |
| `extra_body`   | `object`  | Passed through to NIM (e.g. `chat_template_kwargs`, `reasoning_budget`) |

### Reasoning / thinking toggle

Some NIM models support explicit reasoning via `chat_template_kwargs`:

| Model                          | Toggle key                | Default |
|--------------------------------|---------------------------|---------|
| `nvidia/nemotron-3-ultra-550b-a55b` | `chat_template_kwargs.enable_thinking` | `false` (cleaner output) |
| `deepseek-ai/deepseek-v4-pro`  | `chat_template_kwargs.thinking`        | `false` (NIM card recommendation) |

To test a different reasoning mode without changing source:

```bash
# Copy the test config and point the proxy at it
cp examples/overrides.json /tmp/my-overrides.json
$EDITOR /tmp/my-overrides.json   # flip the flag
NIM_PROXY_OVERRIDES=/tmp/my-overrides.json python3.12 -m uvicorn nim_proxy.app:app --port 8002
```

Or use the bundled thinking-test preset:

```bash
NIM_PROXY_OVERRIDES=examples/overrides-thinking.json python3.12 -m uvicorn nim_proxy.app:app --port 8002
```

**Note on opencode side:** keep `reasoning: false` in opencode model blocks. NIM reasoning models don't emit a separate `reasoning_content` field — they mix reasoning into `content`. Setting `reasoning: true` in opencode makes it try to parse non-existent reasoning tokens and breaks the stream. The proxy is the right place to flip reasoning.

If your request includes `max_tokens` and the override includes `max_tokens`, the larger of the two wins.

## Auto-ranker: self-healing `auto/*` aliases

An hourly job (`auto_ranker/probe.py`, launchd `com.scubamount.nim-ranker`) keeps a set
of alias models pointed at the best NIM model that is actually up right now.

- Aliases: `auto/retain`, `auto/consolidation`, `auto/reflect`. A client asking for
  `auto/retain` is forwarded to whichever model currently wins.
- **Fidelity gate first, latency second.** A candidate must return non-empty
  `content` that parses as JSON in the expected shape. This rejects reasoning models
  (empty `content`) and `response_format` ignorers (e.g. `mistral-small-4`) that a
  pure latency rank would wrongly pick. Survivors are ranked by p50 latency.
- **Restart-free.** The winner is written to the overrides JSON (`$NIM_PROXY_OVERRIDES`),
  which the proxy reads fresh per request. A model going down or a faster one appearing
  self-heals on the next hourly run — no restart, no client config change.
- If **no** candidate passes, the last-good alias is kept (never blanked) and a CRITICAL
  line is logged.

Config (editable, no code change): `auto_ranker/candidates.json` — allowlist per alias,
probe timeout, samples. Audit log: `~/.config/nim-proxy-ranker.log` (JSONL, one run per line).

```bash
./scripts/install-ranker.sh                              # one-time: seed JSON, wire plist, load job
env -u PYTHONPATH .venv/bin/python -m auto_ranker.probe --dry-run   # probe+rank, write nothing
```

Point a client (e.g. hindsight) at `auto/retain` once and leave it — routing lives here now.

## Use with any OpenAI-compatible client

Point your client at:

```
http://127.0.0.1:8001/v1
```

Set `Authorization: Bearer $NVIDIA_API_KEY`. That's it.

## Opencode

In your `opencode.json`, add the nvidia provider block:

```json
"nvidia": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "NVIDIA NIM (via scubamount-nim-proxy)",
  "options": {
    "baseURL": "http://127.0.0.1:8001/v1",
    "apiKey": "{env:NVIDIA_API_KEY}"
  },
  "models": {
      "nvidia/nemotron-3-ultra-550b-a55b": { "name": "Nemotron 3 Ultra 500b A55B" },
      "stepfun-ai/step-3.7-flash": { "name": "Step 3.7 Flash" }
  }
}
```

Full example in `examples/opencode.json.snippet`.

## Update

```bash
./scripts/update.sh
```

Pulls latest, reinstalls dependencies, restarts the proxy.

## Uninstall

```bash
./scripts/autolaunch.sh uninstall
rm -rf ~/code/scubamount-nim-proxy
```

## Project layout

```
nim_proxy/
  __init__.py
  __main__.py       # entry point, uvicorn.run wrapper
  app.py            # FastAPI app, proxy logic
  config.py         # load_overrides(), env var handling
  overrides.py      # default override dict
scripts/
  install.sh
  restart.sh
  update.sh
  autolaunch.sh
examples/
  opencode.json.snippet
  overrides.json
tests/
  test_overrides.py
```

## License

MIT
