"""
Unicorn Hunter - SQLite storage layer (local fallback).
Single table capturing the full idea lifecycle from input to final decision.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "ideas.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            sector_or_idea TEXT NOT NULL,
            user_sources TEXT,
            discovery_output TEXT,
            input_quality_signal TEXT,
            problem_card TEXT,
            solutions_output TEXT,
            initial_evaluation TEXT,
            initial_score INTEGER,
            verification_questions TEXT,
            user_answers TEXT,
            final_evaluation TEXT,
            final_score INTEGER,
            decision TEXT,
            verification_rounds TEXT,
            status TEXT DEFAULT 'in_progress'
        )
    """)
    # Add verification_rounds column if it does not exist (for existing databases)
    try:
        conn.execute("ALTER TABLE ideas ADD COLUMN verification_rounds TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def create_idea(sector_or_idea: str, user_sources: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO ideas (created_at, sector_or_idea, user_sources, status) VALUES (?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), sector_or_idea, user_sources, "in_progress")
    )
    conn.commit()
    idea_id = cur.lastrowid
    conn.close()
    return idea_id


def update_idea(idea_id: int, **fields):
    if not fields:
        return
    conn = get_connection()
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [idea_id]
    conn.execute(f"UPDATE ideas SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_idea(idea_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_ideas(limit: int = 50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, created_at, sector_or_idea, decision, final_score, initial_score, status "
        "FROM ideas ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def from_json(text):
    if not text:
        return None
    return json.loads(text)
