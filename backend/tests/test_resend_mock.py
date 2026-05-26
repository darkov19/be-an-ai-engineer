import pytest
from unittest.mock import patch, MagicMock
import resend

def test_resend_configuration():
    """Verify that resend api key can be configured and library is correctly imported."""
    resend.api_key = "re_test_key_123"
    assert resend.api_key == "re_test_key_123"

@patch("resend.Emails.send")
def test_resend_email_sending_mocked(mock_send):
    """Verify that emails can be sent using a mocked send function."""
    mock_send.return_value = {
        "id": "email_sent_id_999",
        "from": "onboarding@resend.dev",
        "to": "delivered@resend.dev",
    }
    
    resend.api_key = "re_test_key_123"
    params = {
        "from": "onboarding@resend.dev",
        "to": ["delivered@resend.dev"],
        "subject": "Test Email",
        "html": "<strong>This is a test</strong>"
    }
    
    result = resend.Emails.send(params)
    
    assert result["id"] == "email_sent_id_999"
    mock_send.assert_called_once_with(params)
