"""
Unicorn Hunter - One-time migration script from SQLite to Supabase.
Run once locally: python migrate_to_supabase.py
"""

import sqlite3
import os
from pathlib import Path


def load_credentials():
    """Load Supabase credentials from secrets.toml."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
        if secrets_path.exists():
            with open(secrets_path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_URL") and not url:
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("SUPABASE_KEY") and not key:
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not found in secrets.toml")

    return url, key


def migrate():
    url, key = load_credentials()

    from supabase import create_client
    client = create_client(url, key)

    db_path = Path(__file__).parent / "storage" / "ideas.db"
    if not db_path.exists():
        print("No local SQLite database found at storage/ideas.db")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ideas ORDER BY id ASC").fetchall()
    conn.close()

    if not rows:
        print("No ideas found in local SQLite database.")
        return

    print(f"Found {len(rows)} ideas in SQLite. Starting migration...")

    success = 0
    skipped = 0

    for row in rows:
        data = dict(row)
        idea_id = data.pop("id")

        # Check if already exists in Supabase
        existing = client.table("ideas").select("id").eq("id", idea_id).execute()
        if existing.data:
            print(f"  Idea #{idea_id} already exists in Supabase — skipping")
            skipped += 1
            continue

        # Insert with original id
        payload = {"id": idea_id, **{k: v for k, v in data.items() if v is not None}}

        try:
            client.table("ideas").insert(payload).execute()
            print(f"  Idea #{idea_id} migrated: {data['sector_or_idea'][:60]}...")
            success += 1
        except Exception as e:
            print(f"  Idea #{idea_id} FAILED: {e}")

    print(f"\nMigration complete: {success} migrated, {skipped} skipped.")


if __name__ == "__main__":
    migrate()
