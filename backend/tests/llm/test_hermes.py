import pytest
import httpx

from backend.llm.hermes import (
    HermesProxyConnectionError,
    HermesProxyHTTPError,
    HermesProxyResponseError,
    check_hermes_proxy_health,
)


class MockAsyncClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url):
        if self.error:
            raise self.error
        return self.response


class MockResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


@pytest.mark.asyncio
async def test_check_hermes_proxy_health_success(monkeypatch):
    response = MockResponse(payload={"status": "ok"})
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: MockAsyncClient(response=response),
    )

    health = await check_hermes_proxy_health(host="127.0.0.1", port=3000)

    assert health.status_code == 200
    assert health.payload == {"status": "ok"}
    assert health.url == "http://127.0.0.1:3000/health"


@pytest.mark.asyncio
async def test_check_hermes_proxy_health_connection_error(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: MockAsyncClient(error=httpx.ConnectError("refused")),
    )

    with pytest.raises(HermesProxyConnectionError):
        await check_hermes_proxy_health()


@pytest.mark.asyncio
async def test_check_hermes_proxy_health_http_error(monkeypatch):
    response = MockResponse(status_code=503, payload={"status": "down"})
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: MockAsyncClient(response=response),
    )

    with pytest.raises(HermesProxyHTTPError):
        await check_hermes_proxy_health()


@pytest.mark.asyncio
async def test_check_hermes_proxy_health_invalid_json(monkeypatch):
    response = MockResponse(status_code=200, json_error=ValueError("bad json"))
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: MockAsyncClient(response=response),
    )

    with pytest.raises(HermesProxyResponseError):
        await check_hermes_proxy_health()

