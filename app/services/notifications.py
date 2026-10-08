from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def send_owner_alert(message: str) -> tuple[str, str | None]:
    """Send an SMS when Twilio is configured; otherwise record a demo alert."""
    required = (
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
        settings.owner_phone_number,
    )
    if not all(required):
        logger.warning("DEMO URGENT OWNER ALERT: %s", message)
        return "demo_logged", None

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    try:
        response = httpx.post(
            url,
            data={"From": settings.twilio_from_number, "To": settings.owner_phone_number, "Body": message},
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=10,
        )
        response.raise_for_status()
        return "sent", response.json().get("sid")
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("Owner SMS failed")
        return f"failed: {type(exc).__name__}", None
