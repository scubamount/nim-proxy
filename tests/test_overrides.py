"""Tests for per-model override injection."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from nim_proxy.app import app
from nim_proxy.config import load_overrides

client = TestClient(app)

DEFAULT_OVERRIDES = load_overrides()

UPSTREAM = "https://integrate.api.nvidia.com"

BODY = {"model": "nvidia/nemotron-3-ultra-550b-a55b", "messages": [{"role": "user", "content": "hi"}]}


def _capture_post():
    """Return a mock for httpx.AsyncClient.post that records calls."""
    mock = AsyncMock()
    mock.return_value = AsyncMock(
        status_code=200,
        json=lambda: {"id": "test", "choices": [], "usage": {}},
        headers={"content-type": "application/json"},
        aread=AsyncMock(return_value=b'{"id":"test","choices":[],"usage":{}}'),
    )
    return mock


def test_default_override_applied(monkeypatch):
    """Nemotron model gets temperature=1, top_p=0.95, max_tokens=16384, reasoning fields."""
    mock_post = _capture_post()
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    resp = client.post("/v1/chat/completions", json=BODY)
    assert resp.status_code == 200

    args, kwargs = mock_post.call_args
    url = kwargs.get("url", args[0] if args else "")
    assert url.endswith("/v1/chat/completions")

    sent = json.loads(kwargs.get("content", b"{}") or b"{}")
    if not sent:
        sent = kwargs.get("json", {})

    assert sent.get("temperature") == 1
    assert sent.get("top_p") == 0.95
    assert sent.get("max_tokens") == 16384
    assert sent.get("chat_template_kwargs", {}).get("enable_thinking") is True
    assert sent.get("reasoning_budget") == 16384


def test_no_override_unknown_model(monkeypatch):
    """Unknown model passes through without extra fields."""
    mock_post = _capture_post()
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    body = {"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post("/v1/chat/completions", json=body)
    assert resp.status_code == 200

    _, kwargs = mock_post.call_args
    sent = json.loads(kwargs.get("content", b"{}") or b"{}")
    if not sent:
        sent = kwargs.get("json", {})

    assert "chat_template_kwargs" not in sent
    assert "reasoning_budget" not in sent
    assert sent.get("model") == "unknown-model"


def test_path_rewrite(monkeypatch):
    """Upstream URL preserves /v1 (no double /v1/v1)."""
    mock_post = _capture_post()
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    client.post("/v1/chat/completions", json=BODY)

    _, kwargs = mock_post.call_args
    url = kwargs.get("url", "")
    assert url == f"{UPSTREAM}/v1/chat/completions"


def test_max_tokens_cap_override_wins(monkeypatch):
    """When incoming max_tokens < override, override value used."""
    mock_post = _capture_post()
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    body = {**BODY, "max_tokens": 512}
    client.post("/v1/chat/completions", json=body)

    _, kwargs = mock_post.call_args
    sent = json.loads(kwargs.get("content", b"{}") or b"{}")
    if not sent:
        sent = kwargs.get("json", {})
    assert sent.get("max_tokens") == 16384


def test_max_tokens_incoming_wins(monkeypatch):
    """When incoming max_tokens > override, incoming value used."""
    mock_post = _capture_post()
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    body = {**BODY, "max_tokens": 32768}
    client.post("/v1/chat/completions", json=body)

    _, kwargs = mock_post.call_args
    sent = json.loads(kwargs.get("content", b"{}") or b"{}")
    if not sent:
        sent = kwargs.get("json", {})
    assert sent.get("max_tokens") == 32768
