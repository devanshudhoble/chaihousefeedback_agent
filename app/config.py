from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Chai House Feedback Studio")
    public_url: str = os.getenv("APP_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
    database_path: Path = ROOT / os.getenv("DATABASE_PATH", "data/chaihouse-feedback.db")
    upload_dir: Path = ROOT / os.getenv("UPLOAD_DIR", "data/uploads")
    webhook_token: str = os.getenv("WEBHOOK_TOKEN", "")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_decision_model: str = os.getenv("OLLAMA_DECISION_MODEL", "tev1:0.8b")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "tev1:0.8b")
    ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from_number: str = os.getenv("TWILIO_FROM_NUMBER", "")
    owner_phone_number: str = os.getenv("OWNER_PHONE_NUMBER", "+918073464430")
    google_form_url: str = os.getenv("GOOGLE_FORM_URL", "").strip()


settings = Settings()
