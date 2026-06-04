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

If your request includes `max_tokens` and the override includes `max_tokens`, the larger of the two wins.

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
    "nvidia/stepfun-ai/step-3.7-flash": { "name": "Step 3.7 Flash" }
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
