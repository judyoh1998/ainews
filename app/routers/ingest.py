import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import IngestRequest, IngestResponse
from app.services.parser import parse_newsletter

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, status_code=201)
def ingest_newsletter(
    req: IngestRequest, user=Depends(get_current_user), db=Depends(get_db)
):
    if len(req.content) > settings.max_newsletter_size:
        raise HTTPException(
            413, f"Content too large (max {settings.max_newsletter_size} characters)"
        )

    # Validate source_id belongs to user
    if req.source_id:
        src = db.execute(
            "SELECT id FROM sources WHERE id = ? AND user_id = ?",
            (req.source_id, user["id"]),
        ).fetchone()
        if not src:
            raise HTTPException(404, "Source not found")

    # Parse the content
    try:
        articles = parse_newsletter(req.content, req.content_type.value)
        parsed_json = json.dumps(articles)
        parse_status = "parsed"
        parse_error = None
    except Exception as e:
        parsed_json = None
        parse_status = "failed"
        parse_error = str(e)
        articles = []

    cur = db.execute(
        "INSERT INTO ingested_newsletters "
        "(user_id, source_id, raw_content, content_type, parsed_articles, parse_status, parse_error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user["id"],
            req.source_id,
            req.content,
            req.content_type.value,
            parsed_json,
            parse_status,
            parse_error,
        ),
    )
    db.commit()

    return IngestResponse(
        id=cur.lastrowid,
        parse_status=parse_status,
        article_count=len(articles),
        error=parse_error,
    )


@router.post("/ingest/upload", response_model=IngestResponse, status_code=201)
async def ingest_file(
    file: UploadFile,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("latin-1")

    if len(content) > settings.max_newsletter_size:
        raise HTTPException(
            413, f"File too large (max {settings.max_newsletter_size} characters)"
        )

    content_type = "html" if "<html" in content.lower()[:500] else "text"

    try:
        articles = parse_newsletter(content, content_type)
        parsed_json = json.dumps(articles)
        parse_status = "parsed"
        parse_error = None
    except Exception as e:
        parsed_json = None
        parse_status = "failed"
        parse_error = str(e)
        articles = []

    cur = db.execute(
        "INSERT INTO ingested_newsletters "
        "(user_id, raw_content, content_type, parsed_articles, parse_status, parse_error) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user["id"], content, content_type, parsed_json, parse_status, parse_error),
    )
    db.commit()

    return IngestResponse(
        id=cur.lastrowid,
        parse_status=parse_status,
        article_count=len(articles),
        error=parse_error,
    )


@router.get("/ingest/history")
def ingest_history(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.execute(
        "SELECT id, source_id, content_type, parse_status, parse_error, "
        "ingested_at, ingested_date FROM ingested_newsletters "
        "WHERE user_id = ? ORDER BY ingested_at DESC LIMIT 50",
        (user["id"],),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "source_id": r["source_id"],
            "content_type": r["content_type"],
            "parse_status": r["parse_status"],
            "parse_error": r["parse_error"],
            "ingested_at": r["ingested_at"],
            "ingested_date": r["ingested_date"],
        }
        for r in rows
    ]
