"""
Unicorn Hunter - Supabase storage layer.
Replaces SQLite for persistent cloud storage.
Mirrors the same interface as db.py so app.py needs minimal changes.
"""

import os
from datetime import datetime, timezone
from supabase import create_client, Client

TABLE = "ideas"


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        try:
            import streamlit as st
            url = url or st.secrets.get("SUPABASE_URL")
            key = key or st.secrets.get("SUPABASE_KEY")
        except Exception:
            pass

    # Fallback: read secrets.toml directly (handles BOM on Windows)
    if not url or not key:
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".streamlit", "secrets.toml"
        )
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("SUPABASE_URL") and not url:
                            url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("SUPABASE_KEY") and not key:
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_KEY not found. "
            "Add them to .streamlit/secrets.toml or as environment variables."
        )

    return create_client(url, key)


def create_idea(sector_or_idea: str, user_sources: str = "") -> int:
    client = get_supabase()
    result = client.table(TABLE).insert({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sector_or_idea": sector_or_idea,
        "user_sources": user_sources,
        "status": "in_progress",
    }).execute()
    return result.data[0]["id"]


def update_idea(idea_id: int, **fields):
    if not fields:
        return
    client = get_supabase()
    client.table(TABLE).update(fields).eq("id", idea_id).execute()


def get_idea(idea_id: int):
    client = get_supabase()
    result = client.table(TABLE).select("*").eq("id", idea_id).execute()
    return result.data[0] if result.data else None


def list_ideas(limit: int = 50):
    client = get_supabase()
    result = (
        client.table(TABLE)
        .select("id, created_at, sector_or_idea, decision, final_score, initial_score, status")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
