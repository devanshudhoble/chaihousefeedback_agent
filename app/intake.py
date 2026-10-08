"""Restricted public ASGI surface for Google Forms Apps Script intake.

Run this on loopback behind a tunnel. It exposes only the token-protected webhook;
the owner dashboard and the main application's other routes are not mounted here.
"""

from fastapi import FastAPI

from app.db import initialize_database
from app.main import google_form_webhook

app = FastAPI(
    title="Chai House Form Intake",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_api_route("/webhooks/google-form", google_form_webhook, methods=["POST"])


@app.on_event("startup")
def startup() -> None:
    initialize_database()
