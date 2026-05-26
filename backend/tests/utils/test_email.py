import pytest
from unittest.mock import patch, MagicMock
from backend.utils.email import send_email
from backend.config import settings

def test_send_email_dry_run():
    """Verify that send_email operates in dry-run mode when no API key is set."""
    # Ensure resend_api_key is None
    with patch.object(settings, "resend_api_key", None):
        result = send_email("test@example.com", "Test Subject", "<p>Hello</p>")
        assert result is not None
        assert result["status"] == "simulated"
        assert result["to"] == ["test@example.com"]
        assert result["subject"] == "Test Subject"

@patch("resend.Emails.send")
def test_send_email_with_key(mock_send):
    """Verify that send_email calls the resend library when API key is configured."""
    mock_response = MagicMock()
    mock_response.id = "re_email_id_567"
    mock_send.return_value = mock_response
    
    with patch.object(settings, "resend_api_key", "re_test_key_123"):
        # Explicitly set the module-level api key since patch.object on settings doesn't auto-reset module code
        import resend
        resend.api_key = "re_test_key_123"
        
        result = send_email("test@example.com", "Test Subject", "<p>Hello</p>")
        assert result == "re_email_id_567"
        mock_send.assert_called_once_with({
            "from": "onboarding@resend.dev",
            "to": ["test@example.com"],
            "subject": "Test Subject",
            "html": "<p>Hello</p>"
        })
