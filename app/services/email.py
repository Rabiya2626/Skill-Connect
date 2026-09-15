"""Small Resend client using only the Python standard library."""
import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import current_app


def send_email(recipient, subject, html):
    """Send an email without allowing delivery failure to break the user flow."""
    api_key = current_app.config["RESEND_API_KEY"]
    if not api_key:
        current_app.logger.warning("Email delivery is not configured: set RESEND_API_KEY and RESEND_FROM_EMAIL to send %r to %s.", subject, recipient)
        if current_app.debug and current_app.config["EMAIL_DEBUG_LOG_LINKS"]:
            current_app.logger.warning("Development email preview for %s: %s", recipient, html)
        return False
    payload = json.dumps({
        "from": current_app.config["RESEND_FROM_EMAIL"], "to": [recipient],
        "subject": subject, "html": html,
    }).encode()
    request = Request("https://api.resend.com/emails", data=payload, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (URLError, OSError) as error:
        logging.getLogger(__name__).warning("Resend delivery failed: %s", error)
        return False
