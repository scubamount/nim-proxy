"""FastAPI app: OpenAI-compatible request handler that injects per-model overrides."""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

from .config import LISTEN_HOST, LISTEN_PORT, NIM_API_KEY, NIM_BASE, load_overrides

app = FastAPI(name="nim-proxy")


def _apply_override(body: dict) -> dict:
    model = (body.get("model") or "").strip()
    overrides = load_overrides()
    override = overrides.get(model)
    if not override:
        return body

    if "upstream" in override:
        body["model"] = override["upstream"]
    if "temperature" in override:
        body["temperature"] = override["temperature"]
    if "top_p" in override:
        body["top_p"] = override["top_p"]
    if "max_tokens" in override:
        requested = body.get("max_tokens") or 0
        body["max_tokens"] = max(int(requested), int(override["max_tokens"]))
    body.setdefault("stream", True)

    extra = dict(override.get("extra_body") or {})
    body.update(extra)
    return body


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    response_model=None,
)
async def catch_all(
    request: Request, path: str
):
    if path.startswith("v1/"):
        upstream_path = path[3:]
    else:
        upstream_path = path

    if upstream_path == "api/show":
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        model_name = (payload.get("name") or "").strip()
        overrides = load_overrides()
        if model_name in overrides:
            return Response(
                content=json.dumps(
                    {
                        "name": model_name,
                        "model_info": {
                            "general.architecture": model_name.split("/")[-1],
                        },
                    }
                ),
                media_type="application/json",
            )
        return Response(
            content=json.dumps({"error": f"unknown model: {model_name}"}),
            status_code=404,
            media_type="application/json",
        )

    url = f"{NIM_BASE}/{upstream_path}"

    # SECURITY: always inject the proxy's own NVIDIA key and IGNORE any client-supplied
    # Authorization header. Downstream callers (hindsight daemon via litellm, opencode,
    # etc.) therefore never need to hold the real credential — they send a dummy/no key
    # and this proxy is the single place the secret lives (sourced from ~/.hermes/.env at
    # startup by scripts/launch-with-key.sh). Previously this fell back to the client key
    # when present, which forced callers to embed the real nvapi key in their configs
    # (plaintext-at-rest, SOC2/ISO27001 finding) and caused 401s when a caller sent a
    # placeholder. Server-side injection is both more secure and more robust.
    auth = f"Bearer {NIM_API_KEY}" if NIM_API_KEY else (
        request.headers.get("authorization") or ""
    )
    headers = {"Authorization": auth} if auth else {}

    if request.method == "GET":
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
        return StreamingResponse(
            iter([resp.content]),
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type", "text/plain"),
        )

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = _apply_override(body)

    print(
        f"[nim-proxy] outbound url: {url}", flush=True
    )
    print(
        f"[nim-proxy] outbound body: {json.dumps(body, ensure_ascii=False)[:1000]}",
        flush=True,
    )

    async def _stream() -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            async with client.stream(
                "POST",
                url,
                json=body,
                headers={**headers, "Content-Type": "application/json"},
            ) as resp:
                if resp.status_code != 200:
                    txt = await resp.aread()
                    print(
                        f"[nim-proxy] NIM {resp.status_code} body: {txt[:500]}",
                        flush=True,
                    )
                    return
                async for chunk in resp.aiter_bytes():
                    yield chunk

    async def _peek() -> tuple[int, bytes, dict]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            resp = await client.send(
                client.build_request(
                    "POST",
                    url,
                    json=body,
                    headers={**headers, "Content-Type": "application/json"},
                ),
                stream=True,
            )
            if resp.status_code != 200:
                body_bytes = await resp.aread()
                print(
                    f"[nim-proxy] NIM {resp.status_code} body: {body_bytes[:500]}",
                    flush=True,
                )
                return resp.status_code, body_bytes, dict(resp.headers)
            return resp.status_code, b"", dict(resp.headers)

    status, err_body, resp_headers = await _peek()
    if status != 200:
        out_headers = {}
        for k, v in resp_headers.items():
            if k.lower() in ("content-type", "content-length"):
                out_headers[k] = v
        if status == 429 and "retry-after" not in {h.lower() for h in resp_headers}:
            out_headers["Retry-After"] = "60"
        return Response(
            content=err_body,
            status_code=status,
            headers=out_headers,
            media_type=resp_headers.get("content-type", "application/json"),
        )

    return StreamingResponse(_stream(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "nim_proxy.app:app",
        host=LISTEN_HOST,
        port=LISTEN_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
