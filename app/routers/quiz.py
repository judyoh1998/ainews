import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db
from app.models import QuizResponse
from app.services.seed_data import SEED_QUIZ
from app.services.synthesis import get_period_key

router = APIRouter(tags=["quiz"])


@router.get("/quiz", response_model=QuizResponse)
def get_current_quiz(user=Depends(get_current_user), db=Depends(get_db)):
    """Get quiz for the latest digest."""
    row = db.execute(
        "SELECT value FROM preferences WHERE user_id = ? AND key = 'cadence'",
        (user["id"],),
    ).fetchone()
    cadence = row["value"] if row else "daily"

    digest = db.execute(
        "SELECT * FROM digests WHERE user_id = ? AND cadence = ? "
        "AND status IN ('complete', 'partial', 'seed') "
        "ORDER BY created_at DESC LIMIT 1",
        (user["id"], cadence),
    ).fetchone()

    if not digest or not digest["quiz_json"]:
        return QuizResponse(
            period_key=get_period_key(cadence),
            questions=SEED_QUIZ,
        )

    questions = json.loads(digest["quiz_json"])
    return QuizResponse(
        period_key=digest["period_key"],
        questions=questions,
    )


@router.get("/quiz/{period_key}", response_model=QuizResponse)
def get_quiz_by_period(
    period_key: str, user=Depends(get_current_user), db=Depends(get_db)
):
    digest = db.execute(
        "SELECT quiz_json FROM digests WHERE user_id = ? AND period_key = ? "
        "AND status IN ('complete', 'partial', 'seed') "
        "ORDER BY created_at DESC LIMIT 1",
        (user["id"], period_key),
    ).fetchone()

    if not digest or not digest["quiz_json"]:
        raise HTTPException(404, "Quiz not found for this period")

    questions = json.loads(digest["quiz_json"])
    return QuizResponse(period_key=period_key, questions=questions)
