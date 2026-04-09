"""Seed the database with a demo user, sources, and digest."""

import json

from app.auth import _hash_password
from app.database import get_connection, init_db
from app.services.seed_data import SEED_QUIZ, SEED_SOURCES, SEED_STORIES


def seed():
    init_db()
    conn = get_connection()

    # Create demo user (password: "demo123")
    pw_hash = _hash_password("demo123")
    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, email, password_hash) VALUES (1, 'demo', 'demo@neko.news', ?)",
        (pw_hash,),
    )

    # Seed preferences
    conn.execute(
        "INSERT OR IGNORE INTO preferences (user_id, key, value) VALUES (1, 'cadence', 'daily')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO preferences (user_id, key, value) VALUES (1, 'timezone', 'UTC')"
    )

    # Seed sources
    for s in SEED_SOURCES:
        conn.execute(
            "INSERT OR IGNORE INTO sources (user_id, name, source_type) VALUES (1, ?, ?)",
            (s["name"], s["source_type"]),
        )

    # Seed digest
    conn.execute(
        "INSERT OR REPLACE INTO digests (user_id, cadence, period_key, status, stories_json, quiz_json, story_count) "
        "VALUES (1, 'daily', 'demo', 'seed', ?, ?, ?)",
        (json.dumps(SEED_STORIES), json.dumps(SEED_QUIZ), len(SEED_STORIES)),
    )

    conn.commit()
    print(f"Seeded demo user (demo@neko.news / demo123)")
    print(f"Seeded {len(SEED_SOURCES)} sources and 1 demo digest with {len(SEED_STORIES)} stories")


if __name__ == "__main__":
    seed()
