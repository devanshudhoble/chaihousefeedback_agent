from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def jev_decision(feedback: dict) -> dict | None:
    """Ask Ollama's Jev-style decision endpoint for typed triage labels."""
    payload = {
        "model": settings.ollama_decision_model,
        "state": {
            "feedback": feedback.get("comment", ""),
            "food_rating": feedback.get("food_rating"),
            "wait_rating": feedback.get("wait_rating"),
            "ambience_rating": feedback.get("ambience_rating"),
            "staff_rating": feedback.get("staff_rating"),
        },
        "questions": {
            "urgency": {
                "type": "choice",
                "instructions": (
                    "Route only possible immediate health or food-safety reports to emergency. "
                    "Ordinary poor service, taste, or waiting time is improvement."
                ),
                "criteria": {
                    "emergency": "Possible pest/foreign object in food, contamination, allergen issue, illness or injury.",
                    "improvement": "Dissatisfaction with taste, wait, staff, ambience or service without immediate risk.",
                    "routine": "Positive, neutral, or suggestion without a concrete concern.",
                },
            },
            "category": {
                "type": "choice",
                "instructions": "Which single category best matches the main reported feedback?",
                "criteria": {
                    "food_quality": "Taste, temperature, freshness, portion, or quality of food/drinks.",
                    "waiting_time": "Slow service, delays, or long wait for food or the bill.",
                    "staff": "Staff communication, politeness, helpfulness, or service conduct.",
                    "ambience": "Seating, comfort, noise, cleanliness, or atmosphere.",
                    "pest_or_foreign_object": "Possible pest, foreign object, contamination, allergen, or illness report.",
                    "other": "Feedback not covered by the other categories.",
                },
            },
        },
    }
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/v1/systemone",
            json={**payload, "keep_alive": 0},
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        return response.json().get("answers", {})
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("Jev decision unavailable; using deterministic triage: %s", exc)
        return None


def inspect_image(image_path: str) -> str:
    """Ask a configured Ollama vision model if an image appears relevant."""
    path = Path(image_path)
    if not path.is_file():
        return "unclear"
    prompt = (
        "This is an unverified customer photo submitted with a cafe food-safety report. "
        "Classify whether the image visibly appears to support the reported concern, is "
        "unrelated, or is unclear. Do not identify people, claim certainty, infer when or "
        "where it was taken, or make a health determination. Reply with exactly one label: "
        "supports_report, unrelated, unclear."
    )
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_vision_model,
                "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
                "stream": False,
                "keep_alive": 0,
                "options": {"temperature": 0},
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        answer = response.json().get("message", {}).get("content", "").strip().lower()
        for label in ("supports_report", "unrelated", "unclear"):
            if label in answer:
                return label
    except (httpx.HTTPError, OSError, ValueError) as exc:
        logger.info("Image review unavailable; leaving it for owner review: %s", exc)
    return "unclear"


def write_dashboard_summary(metrics: dict) -> str | None:
    """Create a short narrative from precomputed, non-identifying metrics."""
    context = {
        "total_feedback": metrics["total"],
        "average_ratings": metrics["averages"],
        "emergency_count": metrics["emergency_count"],
        "improvement_count": metrics["improvement_count"],
        "top_categories": metrics["top_categories"],
    }
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a concise cafe operations analyst. Use only supplied counts and "
                            "metrics. Do not invent trends or causes. Separate one-off reports from "
                            "recurring patterns. Give one practical next step. Keep the answer under 90 words."
                        ),
                    },
                    {"role": "user", "content": json.dumps(context)},
                ],
                "stream": False,
                "keep_alive": 0,
                "options": {"temperature": 0.2, "num_predict": 120},
            },
            # Keep the owner dashboard responsive if a local model is cold or overloaded.
            timeout=min(settings.ollama_timeout_seconds, 4.0),
        )
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "").strip()
        return text or None
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("Dashboard narrative unavailable; using metric-based summary: %s", exc)
        return None
