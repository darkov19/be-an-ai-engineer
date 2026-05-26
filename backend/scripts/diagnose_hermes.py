#!/usr/bin/env python3
import sys
import httpx
import structlog
from backend.config import settings

logger = structlog.get_logger()

def diagnose_hermes():
    """
    Pings the local Hermes proxy endpoint and prints status details.
    """
    url = f"http://{settings.hermes_host}:{settings.hermes_port}/health"
    logger.info("Starting Hermes proxy diagnostics", target_url=url)
    
    try:
        # Make a quick request with a 2-second timeout
        response = httpx.get(url, timeout=2.0)
        if response.status_code == 200:
            logger.info("Hermes proxy is online and responsive", status_code=200, response=response.json())
            print("\n✅ SUCCESS: Hermes proxy is online and healthy!")
            sys.exit(0)
        else:
            logger.warning("Hermes proxy responded with non-200 code", status_code=response.status_code)
            print(f"\n⚠️ WARNING: Hermes proxy responded with status code {response.status_code}")
            sys.exit(1)
    except httpx.ConnectError:
        logger.error("Failed to connect to Hermes proxy", host=settings.hermes_host, port=settings.hermes_port)
        print(f"\n❌ ERROR: Could not connect to Hermes proxy at {settings.hermes_host}:{settings.hermes_port}.")
        print("Please check that the local tunneling proxy is running and configuration in .env is correct.")
        sys.exit(1)
    except Exception as e:
        logger.error("Hermes proxy health check failed", error=str(e))
        print(f"\n❌ ERROR: Diagnostic check failed with error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    diagnose_hermes()
