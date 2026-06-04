"""FastAPI app: OpenAI-compatible request handler that injects per-model overrides."""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from .config import LISTEN_HOST, LISTEN_PORT, NIM_API_KEY, NIM_BASE, load_overrides

app = FastAPI(name="nim-proxy")


def _apply_override(body: dict) -> dict:
    model = (body.get("model") or "").strip()
    override = load_overrides().get(model)
    if not override:
        return body

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
    "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
async def catch_all(request: Request, path: str) -> StreamingResponse:
    if path.startswith("v1/"):
        upstream_path = path[3:]
    else:
        upstream_path = path
    url = f"{NIM_BASE}/{upstream_path}"

    auth = request.headers.get("authorization") or (
        f"Bearer {NIM_API_KEY}" if NIM_API_KEY else ""
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

    async def _forward() -> AsyncIterator[bytes]:
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
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(_forward(), media_type="text/event-stream")


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
