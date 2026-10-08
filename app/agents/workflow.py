from __future__ import annotations

import logging
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.db import db_session, utc_now
from app.services.llm import inspect_image, jev_decision, write_dashboard_summary
from app.services.notifications import send_owner_alert

logger = logging.getLogger(__name__)

EMERGENCY_TERMS = re.compile(
    r"\b(cockroach|cockroach(es)?|cockroch|roach|insect|worm|maggot|hair|glass|metal|"
    r"plastic|contaminat\w*|allergen|allergic|food poisoning|vomit|sick after|illness|"
    r"foreign object|unsafe food|poison)\b",
    re.IGNORECASE,
)
IMPROVEMENT_TERMS = re.compile(
    r"\b(bad|poor|cold|stale|slow|delay|delayed|long wait|too long|rude|dirty|unclean|"
    r"not good|not fresh|disappoint\w*|complain\w*|issue|problem|improve|missing|wrong|"
    r"unhelpful|uncomfortable|overpriced)\b",
    re.IGNORECASE,
)


class FeedbackState(TypedDict, total=False):
    feedback: dict
    urgency: str
    category: str
    summary: str
    suggested_action: str
    image_status: str
    notification_status: str
    notification_message: str
    analysis: str


class AnalyticsState(TypedDict):
    metrics: dict
    analysis: str


def _decision_label(answers: dict | None) -> str | None:
    if not answers:
        return None
    value = answers.get("urgency", {}).get("choice")
    return value if value in {"emergency", "improvement", "routine"} else None


def _decision_category(answers: dict | None) -> str | None:
    if not answers:
        return None
    value = answers.get("category", {}).get("choice")
    allowed = {"food_quality", "waiting_time", "staff", "ambience", "pest_or_foreign_object", "other"}
    return value if value in allowed else None


def _explicit_hazard(text: str) -> bool:
    for match in EMERGENCY_TERMS.finditer(text):
        preceding = text[max(0, match.start() - 55):match.start()]
        if re.search(r"\b(?:no|not|never|without|didn't|did not|haven't|hasn't)\b(?:\W+\w+){0,3}\W*$", preceding, re.IGNORECASE):
            continue
        return True
    return False


def _fallback_classification(feedback: dict) -> tuple[str, str]:
    text = feedback.get("comment", "")
    ratings = [feedback.get(key, 5) for key in ("food_rating", "wait_rating", "ambience_rating", "staff_rating")]
    if _explicit_hazard(text):
        return "emergency", "pest_or_foreign_object"
    if min(ratings) <= 2:
        keys = ("food_rating", "wait_rating", "ambience_rating", "staff_rating")
        weakest = keys[ratings.index(min(ratings))]
        return "improvement", {
            "food_rating": "food_quality",
            "wait_rating": "waiting_time",
            "ambience_rating": "ambience",
            "staff_rating": "staff",
        }[weakest]
    if min(ratings) <= 3 or IMPROVEMENT_TERMS.search(text):
        lower = text.lower()
        if any(term in lower for term in ("wait", "slow", "time", "late")):
            return "improvement", "waiting_time"
        if any(term in lower for term in ("staff", "rude", "polite", "service", "response")):
            return "improvement", "staff"
        if any(term in lower for term in ("ambience", "noise", "seat", "music")):
            return "improvement", "ambience"
        return "improvement", "food_quality" if min(ratings) <= 3 else "other"
    return "routine", "other"


def _triage_node(state: FeedbackState) -> dict:
    feedback = state["feedback"]
    fallback_urgency, fallback_category = _fallback_classification(feedback)
    answers = jev_decision(feedback)
    model_urgency = _decision_label(answers)

    # Safety policy override: the model cannot downgrade an explicit hazard report.
    if _explicit_hazard(feedback.get("comment", "")):
        urgency = "emergency"
        category = "pest_or_foreign_object"
    else:
        urgency = model_urgency or fallback_urgency
        category = _decision_category(answers) or fallback_category

    return {
        "urgency": urgency,
        "category": category,
        "image_status": "pending" if feedback.get("image_path") else ("reference_only" if feedback.get("image_url") else "no_image"),
    }


def _needs_image_review(state: FeedbackState) -> str:
    if state.get("urgency") == "emergency":
        return "image_review" if state["feedback"].get("image_path") else "emergency_agent"
    return "improvement_agent" if state.get("urgency") == "improvement" else "routine_agent"


def _image_review_node(state: FeedbackState) -> dict:
    return {"image_status": inspect_image(state["feedback"]["image_path"])}


def _after_image_review(state: FeedbackState) -> str:
    return "emergency_agent"


def _emergency_agent_node(state: FeedbackState) -> dict:
    feedback = state["feedback"]
    comment = feedback.get("comment", "").strip()
    summary = (
        f"Customer reported a possible safety concern: {comment[:150]}"
        if comment else "Customer reported a possible food-safety concern."
    )
    action = "Inspect the reported area and follow the cafe food-safety procedure."
    image_status = state.get("image_status", "no_image")
    suffix = " Photo review is inconclusive." if image_status == "unclear" else ""
    if image_status == "supports_report":
        suffix = " Submitted photo appears relevant; it is not independently verified."
    elif image_status == "unrelated":
        suffix = " Submitted photo appears unrelated; text report still needs review."
    elif image_status == "reference_only":
        suffix = " Customer provided a photo link that could not be reviewed automatically."
    message = (
        f"Chai House urgent feedback: a customer reported a possible safety issue. "
        f"{summary[:120]}{suffix} Ref {feedback['id']}."
    )
    # Missing or inconclusive photo never blocks an alert for a credible text report.
    with db_session() as db:
        cursor = db.execute(
            """INSERT OR IGNORE INTO notification_outbox
               (feedback_id, created_at, status, message) VALUES (?, ?, 'queued', ?)""",
            (feedback["id"], utc_now(), message),
        )
        if cursor.rowcount == 0:
            row = db.execute(
                "SELECT status, message FROM notification_outbox WHERE feedback_id=?",
                (feedback["id"],),
            ).fetchone()
            return {
                "notification_status": row["status"] if row else "already_processed",
                "notification_message": row["message"] if row else message,
                "summary": summary,
                "suggested_action": action,
            }
    status, _provider_id = send_owner_alert(message)
    with db_session() as db:
        db.execute(
            "UPDATE notification_outbox SET status=?, provider_id=? WHERE feedback_id=?",
            (status, _provider_id, feedback["id"]),
        )
    return {
        "summary": summary,
        "suggested_action": action,
        "notification_status": status,
        "notification_message": message,
    }


def _improvement_agent_node(state: FeedbackState) -> dict:
    feedback = state["feedback"]
    category = state.get("category", "other")
    actions = {
        "food_quality": "Review food preparation and serving-temperature checks.",
        "waiting_time": "Review peak-hour preparation and order handoff times.",
        "staff": "Review the service interaction with the shift lead.",
        "ambience": "Review seating, cleanliness, noise, and comfort in the reported area.",
        "other": "Review the customer comment and look for a practical service improvement.",
    }
    return {
        "summary": feedback.get("comment", "").strip()[:180] or "Customer gave a low rating and may need follow-up review.",
        "suggested_action": actions.get(category, actions["other"]),
        "notification_status": "not_required",
        "notification_message": "",
    }


def _routine_node(state: FeedbackState) -> dict:
    feedback = state["feedback"]
    return {
        "summary": feedback.get("comment", "").strip()[:180] or "Customer shared ratings without an additional comment.",
        "suggested_action": "Continue monitoring customer ratings.",
        "notification_status": "not_required",
        "notification_message": "",
    }


def _persist_node(state: FeedbackState) -> dict:
    feedback = state["feedback"]
    with db_session() as db:
        db.execute(
            """UPDATE feedback SET urgency=?, category=?, summary=?, suggested_action=?,
               image_status=?, notification_status=?, notification_message=?, processing_status='completed'
               WHERE id=?""",
            (
                state.get("urgency", "routine"), state.get("category", "other"),
                state.get("summary", ""), state.get("suggested_action", ""),
                state.get("image_status", "no_image"), state.get("notification_status", "not_required"),
                state.get("notification_message", ""), feedback["id"],
            ),
        )
    return {}


def build_feedback_graph():
    graph = StateGraph(FeedbackState)
    graph.add_node("jev_triage", _triage_node)
    graph.add_node("image_review", _image_review_node)
    graph.add_node("emergency_agent", _emergency_agent_node)
    graph.add_node("improvement_agent", _improvement_agent_node)
    graph.add_node("routine_agent", _routine_node)
    graph.add_node("persist_result", _persist_node)
    graph.add_edge(START, "jev_triage")
    graph.add_conditional_edges(
        "jev_triage",
        _needs_image_review,
        {
            "image_review": "image_review",
            "emergency_agent": "emergency_agent",
            "improvement_agent": "improvement_agent",
            "routine_agent": "routine_agent",
        },
    )
    graph.add_conditional_edges(
        "image_review",
        _after_image_review,
        {"emergency_agent": "emergency_agent"},
    )
    # All branches converge to persistence after their route-specific work.
    graph.add_edge("emergency_agent", "persist_result")
    graph.add_edge("improvement_agent", "persist_result")
    graph.add_edge("routine_agent", "persist_result")
    graph.add_edge("persist_result", END)
    return graph.compile()


feedback_graph = build_feedback_graph()


def process_feedback(feedback: dict) -> dict:
    return feedback_graph.invoke({"feedback": feedback})


def _dashboard_analyst_node(state: AnalyticsState) -> dict:
    metrics = state["metrics"]
    fallback = (
        f"{metrics['total']} responses received. {metrics['emergency_count']} possible urgent "
        f"safety reports and {metrics['improvement_count']} improvement reports are recorded. "
    )
    if not metrics["total"]:
        return {"analysis": "No feedback has been submitted yet. Share the QR code to begin collecting responses."}
    if metrics["improvement_count"]:
        categories = ", ".join(item["category"].replace("_", " ") for item in metrics["top_categories"][:2])
        fallback += f"Review improvement feedback{f' about {categories}' if categories else ''} with the shift lead."
    else:
        fallback += "Continue monitoring ratings and customer comments."
    return {"analysis": write_dashboard_summary(metrics) or fallback}


def build_analytics_graph():
    graph = StateGraph(AnalyticsState)
    graph.add_node("dashboard_analyst", _dashboard_analyst_node)
    graph.add_edge(START, "dashboard_analyst")
    graph.add_edge("dashboard_analyst", END)
    return graph.compile()


analytics_graph = build_analytics_graph()


def analyze_dashboard(metrics: dict) -> str:
    return analytics_graph.invoke({"metrics": metrics})["analysis"]
