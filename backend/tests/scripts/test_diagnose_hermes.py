from unittest.mock import AsyncMock, patch

import pytest

from backend.llm.hermes import HermesHealth, HermesProxyConnectionError, HermesProxyHTTPError
from backend.scripts.diagnose_hermes import diagnose_hermes_async

@pytest.mark.asyncio
@patch("backend.scripts.diagnose_hermes.check_hermes_proxy_health", new_callable=AsyncMock)
async def test_diagnose_hermes_success(mock_health):
    """Verify that diagnose_hermes exits with 0 on successful HTTP 200 response."""
    mock_health.return_value = HermesHealth(
        url="http://127.0.0.1:3000/health",
        status_code=200,
        payload={"status": "ok", "proxy": "active"},
    )
    
    exit_code = await diagnose_hermes_async()
    
    assert exit_code == 0

@pytest.mark.asyncio
@patch("backend.scripts.diagnose_hermes.check_hermes_proxy_health", new_callable=AsyncMock)
async def test_diagnose_hermes_connection_error(mock_health):
    """Verify that diagnose_hermes exits with 1 on connection error."""
    mock_health.side_effect = HermesProxyConnectionError("Connection refused")
    
    exit_code = await diagnose_hermes_async()
    
    assert exit_code == 1

@pytest.mark.asyncio
@patch("backend.scripts.diagnose_hermes.check_hermes_proxy_health", new_callable=AsyncMock)
async def test_diagnose_hermes_non_200(mock_health):
    """Verify that diagnose_hermes exits with 1 on non-200 response."""
    mock_health.side_effect = HermesProxyHTTPError("Hermes proxy health check returned HTTP 500")
    
    exit_code = await diagnose_hermes_async()
    
    assert exit_code == 1
