from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    FetchResponse,
    PreferenceResponse,
    PreferenceUpdate,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)

router = APIRouter(tags=["sources"])


def _source_response(r) -> SourceResponse:
    return SourceResponse(
        id=r["id"],
        name=r["name"],
        url=r["url"],
        source_type=r["source_type"],
        active=bool(r["active"]),
        created_at=r["created_at"],
        last_fetched_at=r["last_fetched_at"] if "last_fetched_at" in r.keys() else None,
    )


# ── Catalog & Fetch (must be before parameterized routes) ──


@router.get("/sources/catalog")
def get_catalog(user=Depends(get_current_user), db=Depends(get_db)):
    """Return the curated RSS feed catalog, annotated with subscription status."""
    from app.services.seed_data import RSS_CATALOG

    existing = db.execute(
        "SELECT url FROM sources WHERE user_id = ? AND url IS NOT NULL",
        (user["id"],),
    ).fetchall()
    existing_urls = {r["url"] for r in existing}

    return [
        {**entry, "subscribed": entry["url"] in existing_urls}
        for entry in RSS_CATALOG
    ]


@router.post("/sources/fetch", response_model=FetchResponse)
def fetch_sources(user=Depends(get_current_user), db=Depends(get_db)):
    """Pull latest entries from all active RSS feeds for the current user."""
    from app.services.rss_fetcher import fetch_all_rss_sources

    return fetch_all_rss_sources(db, user["id"])


# ── CRUD ──


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.execute(
        "SELECT id, name, url, source_type, active, created_at, last_fetched_at "
        "FROM sources WHERE user_id = ? ORDER BY id",
        (user["id"],),
    ).fetchall()
    return [_source_response(r) for r in rows]


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(
    req: SourceCreate, user=Depends(get_current_user), db=Depends(get_db)
):
    # Prevent duplicate RSS feed URLs
    if req.url:
        dup = db.execute(
            "SELECT id FROM sources WHERE user_id = ? AND url = ?",
            (user["id"], req.url),
        ).fetchone()
        if dup:
            raise HTTPException(409, "Already subscribed to this feed URL")

    cur = db.execute(
        "INSERT INTO sources (user_id, name, url, source_type) VALUES (?, ?, ?, ?)",
        (user["id"], req.name, req.url, req.source_type),
    )
    db.commit()
    row = db.execute(
        "SELECT id, name, url, source_type, active, created_at, last_fetched_at "
        "FROM sources WHERE id = ?",
        (cur.lastrowid,),
    ).fetchone()
    return _source_response(row)


@router.put("/sources/{source_id}", response_model=SourceResponse)
def update_source(
    source_id: int,
    req: SourceUpdate,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    row = db.execute(
        "SELECT * FROM sources WHERE id = ? AND user_id = ?",
        (source_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Source not found")

    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.url is not None:
        updates["url"] = req.url
    if req.active is not None:
        updates["active"] = 1 if req.active else 0

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [source_id, user["id"]]
        db.execute(
            f"UPDATE sources SET {set_clause} WHERE id = ? AND user_id = ?", vals
        )
        db.commit()

    row = db.execute(
        "SELECT id, name, url, source_type, active, created_at, last_fetched_at "
        "FROM sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    return _source_response(row)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: int, user=Depends(get_current_user), db=Depends(get_db)
):
    row = db.execute(
        "SELECT id FROM sources WHERE id = ? AND user_id = ?",
        (source_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Source not found")
    db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    db.commit()


# ── Preferences ──


@router.get("/preferences/{key}", response_model=PreferenceResponse)
def get_preference(key: str, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.execute(
        "SELECT key, value FROM preferences WHERE user_id = ? AND key = ?",
        (user["id"], key),
    ).fetchone()
    if not row:
        defaults = {"cadence": "daily", "timezone": "UTC"}
        if key in defaults:
            return PreferenceResponse(key=key, value=defaults[key])
        raise HTTPException(404, "Preference not found")
    return PreferenceResponse(key=row["key"], value=row["value"])


@router.put("/preferences/{key}", response_model=PreferenceResponse)
def set_preference(
    key: str,
    req: PreferenceUpdate,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    allowed_keys = {"cadence", "timezone"}
    if key not in allowed_keys:
        raise HTTPException(400, f"Unknown preference key. Allowed: {allowed_keys}")
    if key == "cadence" and req.value not in ("daily", "weekly"):
        raise HTTPException(400, "Cadence must be 'daily' or 'weekly'")

    db.execute(
        "INSERT INTO preferences (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = ?, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')",
        (user["id"], key, req.value, req.value),
    )
    db.commit()
    return PreferenceResponse(key=key, value=req.value)
