import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db
from app.models import DigestResponse, GenerateRequest, GenerateResponse
from app.services.seed_data import SEED_STORIES
from app.services.synthesis import generate_digest, get_period_key

router = APIRouter(tags=["digest"])


@router.get("/digest", response_model=DigestResponse)
def get_current_digest(user=Depends(get_current_user), db=Depends(get_db)):
    """Get the latest complete digest for the current user and cadence."""
    row = db.execute(
        "SELECT value FROM preferences WHERE user_id = ? AND key = 'cadence'",
        (user["id"],),
    ).fetchone()
    cadence = row["value"] if row else "daily"

    # Find the latest complete/partial/seed digest
    digest = db.execute(
        "SELECT * FROM digests WHERE user_id = ? AND cadence = ? "
        "AND status IN ('complete', 'partial', 'seed') "
        "ORDER BY created_at DESC LIMIT 1",
        (user["id"], cadence),
    ).fetchone()

    if not digest:
        # Return seed data
        period_key = get_period_key(cadence)
        return DigestResponse(
            period_key=period_key,
            cadence=cadence,
            status="seed",
            story_count=len(SEED_STORIES),
            stories=SEED_STORIES,
            created_at="",
        )

    stories = json.loads(digest["stories_json"]) if digest["stories_json"] else []
    return DigestResponse(
        period_key=digest["period_key"],
        cadence=digest["cadence"],
        status=digest["status"],
        story_count=digest["story_count"],
        stories=stories,
        created_at=digest["created_at"],
    )


@router.get("/digest/{period_key}", response_model=DigestResponse)
def get_digest_by_period(
    period_key: str, user=Depends(get_current_user), db=Depends(get_db)
):
    digest = db.execute(
        "SELECT * FROM digests WHERE user_id = ? AND period_key = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (user["id"], period_key),
    ).fetchone()

    if not digest:
        raise HTTPException(404, "Digest not found")

    stories = json.loads(digest["stories_json"]) if digest["stories_json"] else []
    return DigestResponse(
        period_key=digest["period_key"],
        cadence=digest["cadence"],
        status=digest["status"],
        story_count=digest["story_count"],
        stories=stories,
        created_at=digest["created_at"],
    )



@router.post("/digest/generate", response_model=GenerateResponse)
def trigger_generation(
    req: GenerateRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    row = db.execute(
        "SELECT value FROM preferences WHERE user_id = ? AND key = 'cadence'",
        (user["id"],),
    ).fetchone()
    cadence = row["value"] if row else "daily"
    period_key = req.period_key or get_period_key(cadence)

    # Check for existing digest
    existing = db.execute(
        "SELECT id, status FROM digests WHERE user_id = ? AND cadence = ? AND period_key = ?",
        (user["id"], cadence, period_key),
    ).fetchone()

    if existing and not req.force:
        return GenerateResponse(status="already_exists", digest_id=existing["id"])

    # Run generation synchronously — fast without LLM, acceptable with LLM
    digest_id = generate_digest(db, user["id"], period_key, cadence, req.force)

    # Get final status
    row = db.execute("SELECT status FROM digests WHERE id = ?", (digest_id,)).fetchone()
    status = row["status"] if row else "complete"
    return GenerateResponse(status=status, digest_id=digest_id)
