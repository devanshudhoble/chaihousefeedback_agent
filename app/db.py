from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with db_session() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'qr_form',
                food_rating INTEGER NOT NULL CHECK(food_rating BETWEEN 1 AND 5),
                wait_rating INTEGER NOT NULL CHECK(wait_rating BETWEEN 1 AND 5),
                ambience_rating INTEGER NOT NULL CHECK(ambience_rating BETWEEN 1 AND 5),
                staff_rating INTEGER NOT NULL CHECK(staff_rating BETWEEN 1 AND 5),
                comment TEXT NOT NULL DEFAULT '',
                image_path TEXT,
                image_url TEXT,
                urgency TEXT NOT NULL DEFAULT 'routine',
                category TEXT NOT NULL DEFAULT 'other',
                summary TEXT NOT NULL DEFAULT '',
                suggested_action TEXT NOT NULL DEFAULT '',
                image_status TEXT NOT NULL DEFAULT 'no_image',
                notification_status TEXT NOT NULL DEFAULT 'not_required',
                notification_message TEXT NOT NULL DEFAULT '',
                processing_status TEXT NOT NULL DEFAULT 'received'
            );

            CREATE TABLE IF NOT EXISTS notification_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_id TEXT NOT NULL UNIQUE REFERENCES feedback(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                provider_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_feedback_urgency ON feedback(urgency);
            """
        )


def list_feedback(limit: int = 100) -> list[dict]:
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_feedback(feedback_id: str) -> dict | None:
    with db_session() as db:
        row = db.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
    return dict(row) if row else None


def summarize_feedback() -> dict:
    with db_session() as db:
        total = db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        averages = db.execute(
            """SELECT AVG(food_rating), AVG(wait_rating), AVG(ambience_rating), AVG(staff_rating)
               FROM feedback"""
        ).fetchone()
        counts = db.execute(
            "SELECT urgency, COUNT(*) AS count FROM feedback GROUP BY urgency"
        ).fetchall()
        categories = db.execute(
            """SELECT category, COUNT(*) AS count FROM feedback
               WHERE urgency IN ('improvement', 'emergency')
               GROUP BY category ORDER BY count DESC LIMIT 4"""
        ).fetchall()
        recent = db.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    urgency_counts = {row["urgency"]: row["count"] for row in counts}
    return {
        "total": total,
        "averages": {
            "food": round(averages[0] or 0, 1),
            "wait": round(averages[1] or 0, 1),
            "ambience": round(averages[2] or 0, 1),
            "staff": round(averages[3] or 0, 1),
        },
        "emergency_count": urgency_counts.get("emergency", 0),
        "improvement_count": urgency_counts.get("improvement", 0),
        "routine_count": urgency_counts.get("routine", 0),
        "top_categories": [dict(row) for row in categories],
        "recent": [dict(row) for row in recent],
    }


def seed_demo_feedback() -> None:
    now = datetime.now(timezone.utc)
    demo = [
        (
            "demo-1", (now.replace(hour=10)).isoformat(timespec="seconds"), "demo",
            5, 4, 5, 5, "Loved the filter coffee and the calm seating.", None,
            "routine", "food_quality", "Customer praised the filter coffee and seating.",
            "Keep the coffee and seating experience consistent.", "no_image", "not_required",
            "", "completed",
        ),
        (
            "demo-2", (now.replace(hour=11)).isoformat(timespec="seconds"), "demo",
            2, 2, 4, 3, "Food took a long time and arrived cold.", None,
            "improvement", "waiting_time", "Customer reported a long wait and cold food.",
            "Review peak-hour handoff time and food temperature checks.", "no_image",
            "not_required", "", "completed",
        ),
        (
            "demo-3", (now.replace(hour=12)).isoformat(timespec="seconds"), "demo",
            3, 4, 3, 2, "Staff did not respond politely when I asked about my order.", None,
            "improvement", "staff", "Customer reported an unhelpful response about an order.",
            "Review the service interaction with the shift lead.", "no_image", "not_required",
            "", "completed",
        ),
        (
            "demo-4", (now.replace(hour=13)).isoformat(timespec="seconds"), "demo",
            1, 4, 3, 3, "I think I saw a cockroach near my food; please check this.", None,
            "emergency", "pest_or_foreign_object",
            "Customer reported a possible cockroach near food; the report is unverified.",
            "Inspect the reported area and follow the cafe food-safety procedure.",
            "no_image", "demo_logged",
            "Chai House urgent feedback: a customer reported a possible cockroach near food. Please review promptly. Ref demo-4.",
            "completed",
        ),
    ]
    with db_session() as db:
        count = db.execute("SELECT COUNT(*) FROM feedback WHERE source='demo'").fetchone()[0]
        if count:
            return
        db.executemany(
            """INSERT OR IGNORE INTO feedback
               (id, created_at, source, food_rating, wait_rating, ambience_rating,
                staff_rating, comment, image_path, urgency, category, summary,
                suggested_action, image_status, notification_status,
                notification_message, processing_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            demo,
        )
        db.executemany(
            """INSERT OR IGNORE INTO notification_outbox
               (feedback_id, created_at, status, message)
               VALUES (?, ?, ?, ?)""",
            [("demo-4", utc_now(), "demo_logged", demo[3][15])],
        )
