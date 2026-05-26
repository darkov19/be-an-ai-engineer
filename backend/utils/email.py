import resend
import structlog
from typing import List, Union
from backend.config import settings

logger = structlog.get_logger()

# Set API key at module level if present
if settings.resend_api_key:
    resend.api_key = settings.resend_api_key
else:
    logger.warning("Resend API key not configured. Email dispatch will operate in dry-run mode.")

def send_email(
    to: Union[str, List[str]],
    subject: str,
    html: str,
    from_email: str = "onboarding@resend.dev"
) -> Union[dict, None]:
    """
    Sends an email using Resend.
    If the API key is not configured, logs a mock output and runs in dry-run mode.
    """
    to_list = [to] if isinstance(to, str) else to
    
    params = {
        "from": from_email,
        "to": to_list,
        "subject": subject,
        "html": html,
    }
    
    if not settings.resend_api_key:
        logger.info(
            "Dry-run: Email dispatch simulated successfully",
            to=to_list,
            subject=subject,
            from_email=from_email
        )
        # Return a simulated successful response
        return {
            "id": "dry_run_simulated_id",
            "status": "simulated",
            "to": to_list,
            "subject": subject
        }
        
    try:
        logger.info("Attempting email dispatch via Resend", to=to_list, subject=subject)
        email = resend.Emails.send(params)
        logger.info("Email dispatched successfully", email_id=getattr(email, "id", None))
        return getattr(email, "id", None)
    except Exception as e:
        logger.error("Failed to send email via Resend", error=str(e), to=to_list, subject=subject)
        raise e
