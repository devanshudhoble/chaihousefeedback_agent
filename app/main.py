from __future__ import annotations

import logging
import re
import uuid
import hashlib
import json
import base64
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agents.workflow import analyze_dashboard, process_feedback
from app.config import ROOT, settings
from app.db import db_session, get_feedback, initialize_database, seed_demo_feedback, summarize_feedback, utc_now

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Local-first customer feedback triage and dashboard prototype for Chai House.",
    version="0.1.0",
)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
static_dir = ROOT / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    seed_demo_feedback()
    _create_qr()


def _create_qr() -> None:
    destination = static_dir / "qr-feedback.png"
    if settings.google_form_url:
        qrcode.make(settings.google_form_url, box_size=10, border=3).save(destination)
    elif destination.exists():
        # Never leave a stale QR visible as if it pointed to the configured Google Form.
        destination.unlink()


def _validate_rating(value: int, label: str) -> int:
    if value < 1 or value > 5:
        raise HTTPException(status_code=422, detail=f"{label} rating must be from 1 to 5")
    return value


def _insert_feedback(record: dict) -> None:
    with db_session() as db:
        db.execute(
            """INSERT OR IGNORE INTO feedback
               (id, created_at, source, food_rating, wait_rating, ambience_rating,
                staff_rating, comment, image_path, image_url, processing_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'received')""",
            (
                record["id"], record["created_at"], record["source"], record["food_rating"],
                record["wait_rating"], record["ambience_rating"], record["staff_rating"],
                record["comment"], record.get("image_path"), record.get("image_url"),
            ),
        )


def _process_record(record: dict) -> dict:
    try:
        process_feedback(record)
    except Exception as exc:
        logger.exception("Feedback workflow failed for %s", record["id"])
        with db_session() as db:
            db.execute(
                "UPDATE feedback SET processing_status='needs_review', summary=? WHERE id=?",
                (f"Automatic analysis could not complete ({type(exc).__name__}); owner review required.", record["id"]),
            )
    return get_feedback(record["id"]) or record


def _new_record(
    *, food_rating: int, wait_rating: int, ambience_rating: int, staff_rating: int,
    comment: str, source: str, image_path: str | None = None, image_url: str | None = None,
    record_id: str | None = None,
) -> dict:
    return {
        "id": record_id or uuid.uuid4().hex[:10].upper(),
        "created_at": utc_now(),
        "source": source,
        "food_rating": _validate_rating(food_rating, "Food"),
        "wait_rating": _validate_rating(wait_rating, "Waiting time"),
        "ambience_rating": _validate_rating(ambience_rating, "Ambience"),
        "staff_rating": _validate_rating(staff_rating, "Staff"),
        "comment": comment.strip()[:2000],
        "image_path": image_path,
        "image_url": image_url,
    }


def _rating_value(named_values: dict, *labels: str, default: int = 3) -> int:
    values = {str(key).strip().lower(): value for key, value in named_values.items()}
    for label in labels:
        for key, value in values.items():
            if label.lower() in key:
                raw = value[0] if isinstance(value, list) and value else value
                match = re.search(r"[1-5]", str(raw))
                if match:
                    return int(match.group(0))
                word = str(raw).strip().lower()
                return {"poor": 2, "bad": 2, "okay": 3, "average": 3, "good": 4, "excellent": 5}.get(word, default)
    return default


def _comment_value(named_values: dict) -> str:
    for key, value in named_values.items():
        label = str(key).lower()
        if any(token in label for token in ("comment", "feedback", "anything else", "written")):
            return str(value[0] if isinstance(value, list) and value else value)
    return ""


def _google_drive_url(value: object) -> str | None:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme == "https" and parsed.hostname in {"drive.google.com", "docs.google.com"}:
        return candidate[:2000]
    return None


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, view: str = "all"):
    metrics = summarize_feedback()
    records = metrics["recent"]
    if view == "emergency":
        records = [row for row in records if row["urgency"] == "emergency"]
    elif view == "improvement":
        records = [row for row in records if row["urgency"] == "improvement"]
    for item in records:
        image_path = item.get("image_path")
        item["photo_src"] = f"/uploads/{Path(image_path).name}" if image_path else None
    narrative = analyze_dashboard(metrics)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "app_name": settings.app_name,
            "metrics": metrics,
            "records": records,
            "view": view,
            "narrative": narrative,
            "form_url": settings.google_form_url or f"{settings.public_url}/feedback",
            "google_form_configured": bool(settings.google_form_url),
            "sms_configured": all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number, settings.owner_phone_number)),
            "owner_phone": settings.owner_phone_number,
        },
    )


@app.get("/feedback", response_class=HTMLResponse)
def feedback_form(request: Request, demo: bool = False):
    if settings.google_form_url and not demo:
        return RedirectResponse(settings.google_form_url, status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="feedback.html",
        context={"request": request, "app_name": settings.app_name},
    )


@app.post("/feedback")
def submit_feedback_form(
    food_rating: int = Form(...),
    wait_rating: int = Form(...),
    ambience_rating: int = Form(...),
    staff_rating: int = Form(...),
    comment: str = Form(""),
    image: UploadFile | None = File(default=None),
):
    image_path = None
    if image and image.filename:
        content_type = (image.content_type or "").lower()
        if content_type not in IMAGE_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP photo")
        contents = image.file.read(MAX_IMAGE_BYTES + 1)
        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Photo must be 5 MB or smaller")
        if not contents:
            raise HTTPException(status_code=400, detail="The selected photo is empty")
        filename = f"{uuid.uuid4().hex}{IMAGE_EXTENSIONS[content_type]}"
        destination = settings.upload_dir / filename
        destination.write_bytes(contents)
        image_path = str(destination)

    record = _new_record(
        food_rating=food_rating,
        wait_rating=wait_rating,
        ambience_rating=ambience_rating,
        staff_rating=staff_rating,
        comment=comment,
        source="qr_form",
        image_path=image_path,
    )
    _insert_feedback(record)
    _process_record(record)
    return RedirectResponse("/thank-you", status_code=303)


@app.get("/thank-you", response_class=HTMLResponse)
def thank_you(request: Request):
    return templates.TemplateResponse(request=request, name="thank_you.html", context={})


@app.post("/api/feedback")
def api_feedback(payload: dict):
    try:
        record = _new_record(
            food_rating=int(payload.get("food_rating", 3)),
            wait_rating=int(payload.get("wait_rating", 3)),
            ambience_rating=int(payload.get("ambience_rating", 3)),
            staff_rating=int(payload.get("staff_rating", 3)),
            comment=str(payload.get("comment", "")),
            source="api",
            image_url=payload.get("image_url"),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Ratings must be whole numbers from 1 to 5") from exc
    _insert_feedback(record)
    result = _process_record(record)
    result.pop("image_path", None)
    return JSONResponse(result, status_code=201)


@app.post("/webhooks/google-form")
async def google_form_webhook(request: Request, x_webhook_token: str | None = Header(default=None)):
    if not settings.webhook_token:
        raise HTTPException(status_code=503, detail="Set WEBHOOK_TOKEN before enabling the Google Form webhook")
    if x_webhook_token != settings.webhook_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Expected a JSON form-submit payload") from exc
    named_values = payload.get("namedValues", payload)
    stable_payload = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    form_submission_id = "GF" + hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()[:10].upper()
    image_path = None
    image_payload = payload.get("image")
    if isinstance(image_payload, dict) and image_payload.get("base64"):
        content_type = str(image_payload.get("content_type", "")).lower()
        if content_type not in IMAGE_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Google Form photo must be JPG, PNG, or WebP")
        try:
            image_bytes = base64.b64decode(image_payload["base64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Google Form photo encoding is invalid") from exc
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Google Form photo must be non-empty and 5 MB or smaller")
        image_name = f"{uuid.uuid4().hex}{IMAGE_EXTENSIONS[content_type]}"
        image_destination = settings.upload_dir / image_name
        image_destination.write_bytes(image_bytes)
        image_path = str(image_destination)
    record = _new_record(
        food_rating=_rating_value(named_values, "food", "taste"),
        wait_rating=_rating_value(named_values, "wait", "waiting"),
        ambience_rating=_rating_value(named_values, "ambience", "ambiance"),
        staff_rating=_rating_value(named_values, "staff", "service"),
        comment=_comment_value(named_values),
        source="google_form",
        image_url=_google_drive_url(payload.get("image_url")),
        image_path=image_path,
        record_id=form_submission_id,
    )
    _insert_feedback(record)
    result = _process_record(record)
    return {"accepted": True, "feedback_id": record["id"], "urgency": result.get("urgency")}


@app.get("/api/dashboard")
def dashboard_api():
    metrics = summarize_feedback()
    return {**metrics, "analysis": analyze_dashboard(metrics)}


@app.get("/health")
def health():
    with db_session() as db:
        db.execute("SELECT 1").fetchone()
    return {"status": "ok", "app": settings.app_name, "database": "ok", "langgraph": "ready"}


@app.get("/api/qr")
def qr_info():
    return {
        "configured": bool(settings.google_form_url),
        "url": settings.google_form_url or None,
        "image": "/static/qr-feedback.png" if settings.google_form_url else None,
    }


@app.get("/api/feedback/{feedback_id}")
def feedback_detail(feedback_id: str):
    result = get_feedback(feedback_id)
    if not result:
        raise HTTPException(status_code=404, detail="Feedback not found")
    result.pop("image_path", None)
    return result
