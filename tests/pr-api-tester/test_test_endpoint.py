"""
Tests for test_endpoint() in pr-api-tester/server.py.
All HTTP calls are mocked — no live network.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import server


def _entry(method="GET", url="https://api.example.com/v1/items",
           path_params=None, query_params=None,
           response_schema=None, example_request=None):
    return {
        "endpoint_id":    "test_item",
        "component":      "TestItemComponent",
        "method":         method,
        "url_template":   url,
        "path_params":    path_params or [],
        "query_params":   query_params or [],
        "headers":        {"Authorization": "Bearer {token}"},
        "body_schema":    None,
        "response_schema": response_schema,
        "example_request": example_request or {},
        "example_response": {},
        "notes":          "",
        "status":         "EXTRACTED",
    }


def _mock_response(status_code, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


# ── Happy path 200 ─────────────────────────────────────────────────────────────

def test_test_endpoint_200_validated():
    body = json.dumps({"id": "abc", "name": "Board A"})
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(return_value=_mock_response(200, body))
        mock_client_cls.return_value = mock_client

        result = asyncio.run(server.test_endpoint(_entry(), token="tok123"))

    assert result["tag"] == "VALIDATED"
    assert result["validated"] is True
    assert result["status_code"] == 200


# ── 404 → FAILED ──────────────────────────────────────────────────────────────

def test_test_endpoint_404_failed():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(return_value=_mock_response(404, '{"error":"not found"}'))
        mock_client_cls.return_value = mock_client

        result = asyncio.run(server.test_endpoint(_entry(), token="tok123"))

    assert result["tag"] == "FAILED"
    assert result["validated"] is False


# ── 401 → FAILED ──────────────────────────────────────────────────────────────

def test_test_endpoint_401_failed():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(return_value=_mock_response(401, '{"error":"unauthorized"}'))
        mock_client_cls.return_value = mock_client

        result = asyncio.run(server.test_endpoint(_entry(), token="bad_token"))

    assert result["tag"] == "FAILED"
    assert result["status_code"] == 401


# ── 429 backoff → PARTIAL after max retries ────────────────────────────────────

def test_test_endpoint_429_partial_after_max_retries():
    with patch("httpx.AsyncClient") as mock_client_cls, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(return_value=_mock_response(429, '{"error":"rate limited"}'))
        mock_client_cls.return_value = mock_client

        result = asyncio.run(server.test_endpoint(_entry(), token="tok123"))

    assert result["tag"] == "PARTIAL"
    assert result["status_code"] == 429
    assert mock_sleep.call_count == server.RETRY_LIMIT  # exponential sleep called for each retry


# ── Timeout → FAILED after retry ──────────────────────────────────────────────

def test_test_endpoint_timeout_failed_after_retry():
    import httpx
    with patch("httpx.AsyncClient") as mock_client_cls, \
         patch("asyncio.sleep", new_callable=AsyncMock):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        result = asyncio.run(server.test_endpoint(_entry(), token="tok123"))

    assert result["tag"] == "FAILED"
    assert "timeout" in result["error"].lower()


# ── Missing seed ID → FAILED before request ───────────────────────────────────

def test_test_endpoint_missing_path_param_fails_without_request():
    entry = _entry(
        url="https://api.example.com/v2/boards/{board_id}",
        path_params=[{"name": "board_id", "type": "string", "required": True}]
    )
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        result = asyncio.run(server.test_endpoint(entry, token="tok123", seed_ids={}))

    assert result["tag"] == "FAILED"
    assert "board_id" in result["error"]
    mock_client.request.assert_not_called() if hasattr(mock_client, "request") else None


# ── Token substitution in headers ─────────────────────────────────────────────

def test_test_endpoint_token_substituted_in_headers():
    captured_headers = {}

    async def capture_request(method, url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return _mock_response(200, '{"ok": true}')

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(side_effect=capture_request)
        mock_client_cls.return_value = mock_client

        asyncio.run(server.test_endpoint(_entry(), token="my_secret_token"))

    assert "my_secret_token" in captured_headers.get("Authorization", "")


# ── POST body uses example_request ────────────────────────────────────────────

def test_test_endpoint_post_sends_example_body():
    example = {"name": "New Board", "description": "Test"}
    entry = _entry(method="POST", example_request=example)
    captured_json = {}

    async def capture_request(method, url, **kwargs):
        captured_json.update(kwargs.get("json") or {})
        return _mock_response(201, json.dumps({"id": "new123"}))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.request    = AsyncMock(side_effect=capture_request)
        mock_client_cls.return_value = mock_client

        asyncio.run(server.test_endpoint(entry, token="tok123"))

    assert captured_json == example
