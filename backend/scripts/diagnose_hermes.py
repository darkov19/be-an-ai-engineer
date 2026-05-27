#!/usr/bin/env python3
import asyncio
import sys
import structlog

from backend.llm.hermes import (
    HermesProxyConnectionError,
    HermesProxyError,
    HermesProxyHTTPError,
    check_hermes_proxy_health,
)

logger = structlog.get_logger()


async def diagnose_hermes_async() -> int:
    """
    Pings the local Hermes proxy endpoint and prints status details.
    """
    try:
        health = await check_hermes_proxy_health()
    except HermesProxyConnectionError as exc:
        print(f"\nERROR: {exc}")
        print("Please check that the local tunneling proxy is running and configuration in .env is correct.")
        return 1
    except HermesProxyHTTPError as exc:
        print(f"\nWARNING: {exc}")
        return 1
    except HermesProxyError as exc:
        print(f"\nERROR: Diagnostic check failed: {exc}")
        return 1
    except Exception as exc:
        logger.error("Hermes proxy health check failed unexpectedly", error=str(exc))
        print(f"\nERROR: Diagnostic check failed unexpectedly: {exc}")
        return 1

    logger.info("Hermes proxy diagnostic succeeded", status_code=health.status_code, response=health.payload)
    print("\nSUCCESS: Hermes proxy is online and healthy.")
    return 0


def diagnose_hermes():
    sys.exit(asyncio.run(diagnose_hermes_async()))

if __name__ == "__main__":
    diagnose_hermes()
