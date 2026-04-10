import sqlite3
import threading
from pathlib import Path

from app.config import settings

_local = threading.local()

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT,
    source_type TEXT NOT NULL DEFAULT 'newsletter',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS preferences (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS ingested_newsletters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    raw_content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text',
    parsed_articles TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    parse_error TEXT,
    ingested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ingested_date TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d', 'now')),
    ingested_week TEXT NOT NULL DEFAULT (strftime('%Y-W%W', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_newsletters_user_date
    ON ingested_newsletters(user_id, ingested_date);
CREATE INDEX IF NOT EXISTS idx_newsletters_user_week
    ON ingested_newsletters(user_id, ingested_week);

CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cadence TEXT NOT NULL,
    period_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    stories_json TEXT,
    quiz_json TEXT,
    story_count INTEGER DEFAULT 0,
    error_log TEXT,
    source_newsletter_ids TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    completed_at TEXT,
    UNIQUE(user_id, cadence, period_key)
);

CREATE INDEX IF NOT EXISTS idx_digests_user_period
    ON digests(user_id, cadence, period_key);
"""


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    # Migrations for new columns (safe to run repeatedly)
    for stmt in [
        "ALTER TABLE ingested_newsletters ADD COLUMN entry_url TEXT",
        "ALTER TABLE sources ADD COLUMN last_fetched_at TEXT",
    ]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_newsletters_user_entry_url "
        "ON ingested_newsletters(user_id, entry_url) WHERE entry_url IS NOT NULL"
    )
    # Fix broken catalog URLs for existing users
    _url_fixes = [
        ("https://ai.meta.com/blog/rss/", None),  # removed
        ("https://openai.com/blog/rss.xml", "https://openai.com/news/rss.xml"),
        ("https://openai.com/index/rss.xml", "https://openai.com/news/rss.xml"),
        ("https://deepmind.google/blog/rss.xml", None),  # removed
        ("https://deepmind.google/blog/rss/", None),  # removed
        ("https://blog.google/technology/ai/rss/", "https://blog.google/technology/ai/rss"),
        ("https://feeds.arstechnica.com/arstechnica/features", "https://arstechnica.com/ai/feed/"),
        ("https://www.technologyreview.com/topic/artificial-intelligence/feed", None),  # removed
    ]
    for old_url, new_url in _url_fixes:
        if new_url:
            conn.execute("UPDATE sources SET url = ? WHERE url = ?", (new_url, old_url))
        else:
            conn.execute("DELETE FROM sources WHERE url = ?", (old_url,))
    # Remove retired sources
    _remove_urls = [
        "%nitter.poast.org%",
        "%anthropic.com/rss%",
        "%huggingface.co/blog%",
        "%engineering.fb.com%",
        "%reddit.com/r/%",
        "%arxiv.org%",
    ]
    for pattern in _remove_urls:
        conn.execute("DELETE FROM sources WHERE url LIKE ?", (pattern,))
    # Remove any RSS sources whose URL is not in the current catalog
    from app.services.seed_data import RSS_CATALOG
    catalog_urls = {e["url"] for e in RSS_CATALOG}
    all_rss = conn.execute(
        "SELECT id, url FROM sources WHERE source_type = 'rss' AND url IS NOT NULL"
    ).fetchall()
    for row in all_rss:
        if row["url"] not in catalog_urls:
            conn.execute("DELETE FROM sources WHERE id = ?", (row["id"],))
    conn.commit()


def get_db():
    return get_connection()
