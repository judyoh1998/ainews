from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    PreferenceResponse,
    PreferenceUpdate,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.execute(
        "SELECT id, name, url, source_type, active, created_at "
        "FROM sources WHERE user_id = ? ORDER BY id",
        (user["id"],),
    ).fetchall()
    return [
        SourceResponse(
            id=r["id"],
            name=r["name"],
            url=r["url"],
            source_type=r["source_type"],
            active=bool(r["active"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(
    req: SourceCreate, user=Depends(get_current_user), db=Depends(get_db)
):
    cur = db.execute(
        "INSERT INTO sources (user_id, name, url, source_type) VALUES (?, ?, ?, ?)",
        (user["id"], req.name, req.url, req.source_type),
    )
    db.commit()
    row = db.execute("SELECT * FROM sources WHERE id = ?", (cur.lastrowid,)).fetchone()
    return SourceResponse(
        id=row["id"],
        name=row["name"],
        url=row["url"],
        source_type=row["source_type"],
        active=bool(row["active"]),
        created_at=row["created_at"],
    )


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

    row = db.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    return SourceResponse(
        id=row["id"],
        name=row["name"],
        url=row["url"],
        source_type=row["source_type"],
        active=bool(row["active"]),
        created_at=row["created_at"],
    )


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
        # Return defaults
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
