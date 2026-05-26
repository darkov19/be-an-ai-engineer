import pytest
import httpx
from unittest.mock import patch, MagicMock
from backend.scripts.diagnose_hermes import diagnose_hermes

@patch("httpx.get")
@patch("sys.exit")
def test_diagnose_hermes_success(mock_exit, mock_get):
    """Verify that diagnose_hermes exits with 0 on successful HTTP 200 response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok", "proxy": "active"}
    mock_get.return_value = mock_response
    
    diagnose_hermes()
    
    mock_exit.assert_called_once_with(0)

@patch("httpx.get")
@patch("sys.exit")
def test_diagnose_hermes_connection_error(mock_exit, mock_get):
    """Verify that diagnose_hermes exits with 1 on connection error."""
    mock_get.side_effect = httpx.ConnectError("Connection refused")
    
    diagnose_hermes()
    
    mock_exit.assert_called_once_with(1)

@patch("httpx.get")
@patch("sys.exit")
def test_diagnose_hermes_non_200(mock_exit, mock_get):
    """Verify that diagnose_hermes exits with 1 on non-200 response."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response
    
    diagnose_hermes()
    
    mock_exit.assert_called_once_with(1)
