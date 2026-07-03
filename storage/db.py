"""
Unicorn Hunter - Storage layer (local SQLite).
Single table that captures the full idea lifecycle from input to final decision.
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

            -- Input
            sector_or_idea TEXT NOT NULL,
            user_sources TEXT,

            -- Agent 1: Discovery
            discovery_output TEXT,
            input_quality_signal TEXT,

            -- Agent 2: Problem Framing
            problem_card TEXT,

            -- Agent 3: Solution Generation
            solutions_output TEXT,

            -- Agent 4: Evaluation (single cycle in v1)
            initial_evaluation TEXT,
            initial_score INTEGER,
            verification_questions TEXT,
            user_answers TEXT,
            final_evaluation TEXT,
            final_score INTEGER,

            -- Decision
            decision TEXT,

            status TEXT DEFAULT 'in_progress'
        )
    """)
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
    """Flexible update for any columns — pass field name as keyword argument."""
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
