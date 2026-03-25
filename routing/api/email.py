"""
CartPath — Email Service
==========================
Sends verification codes via SMTP.
Falls back to console logging in development.
"""

import os
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("CARTPATH_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("CARTPATH_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("CARTPATH_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("CARTPATH_SMTP_PASSWORD", "")
FROM_EMAIL = os.environ.get("CARTPATH_FROM_EMAIL", "noreply@cartpath.app")


def send_verification_email(to_email: str, code: str) -> bool:
    """Send a 6-digit verification code to the given email address."""
    subject = f"CartPath sign-in code: {code}"
    body = (
        f"Your CartPath verification code is:\n\n"
        f"    {code}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email."
    )

    if not SMTP_HOST:
        # Development mode — log to console
        logger.warning("SMTP not configured. Verification code for %s: %s", to_email, code)
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
        return False
