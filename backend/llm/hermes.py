from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()


class HermesProxyError(RuntimeError):
    """Base class for Hermes proxy health failures."""


class HermesProxyConnectionError(HermesProxyError):
    """Raised when the Hermes proxy cannot be reached."""


class HermesProxyHTTPError(HermesProxyError):
    """Raised when the Hermes proxy returns an unhealthy HTTP status."""


class HermesProxyResponseError(HermesProxyError):
    """Raised when the Hermes proxy health response cannot be parsed."""


@dataclass(frozen=True)
class HermesHealth:
    url: str
    status_code: int
    payload: dict[str, Any]


def hermes_health_url(host: str | None = None, port: int | None = None) -> str:
    resolved_host = host or settings.hermes_host
    resolved_port = port or settings.hermes_port
    return f"http://{resolved_host}:{resolved_port}/health"


async def check_hermes_proxy_health(
    host: str | None = None,
    port: int | None = None,
    timeout: float = 2.0,
) -> HermesHealth:
    """Verify that the local Hermes proxy is reachable before LLM batch work."""
    url = hermes_health_url(host, port)
    logger.info("Starting Hermes proxy health check", target_url=url)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.error("Hermes proxy connection failed", target_url=url, error=str(exc))
        raise HermesProxyConnectionError(f"Could not connect to Hermes proxy at {url}") from exc
    except httpx.HTTPError as exc:
        logger.error("Hermes proxy request failed", target_url=url, error=str(exc))
        raise HermesProxyConnectionError(f"Hermes proxy request failed for {url}: {exc}") from exc

    if response.status_code != 200:
        logger.error("Hermes proxy unhealthy status", target_url=url, status_code=response.status_code)
        raise HermesProxyHTTPError(
            f"Hermes proxy health check returned HTTP {response.status_code} for {url}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("Hermes proxy invalid health response", target_url=url, error=str(exc))
        raise HermesProxyResponseError(f"Hermes proxy health response was not valid JSON for {url}") from exc

    if not isinstance(payload, dict):
        logger.error("Hermes proxy health response was not an object", target_url=url, payload=payload)
        raise HermesProxyResponseError(f"Hermes proxy health response was not a JSON object for {url}")

    logger.info("Hermes proxy is healthy", target_url=url, status_code=response.status_code)
    return HermesHealth(url=url, status_code=response.status_code, payload=payload)

