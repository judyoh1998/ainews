"""Digest generation pipeline: parse → synthesize → quiz."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.prompts import extract as extract_prompt
from app.prompts import quiz as quiz_prompt
from app.prompts import synthesize as synth_prompt
from app.services.llm import LLMService, LLMUnavailableError, get_llm_service
from app.services.parser import parse_newsletter
from app.services.seed_data import SEED_QUIZ, SEED_STORIES

logger = logging.getLogger(__name__)


def get_period_key(cadence: str, tz_name: str = "UTC") -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    now = datetime.now(tz)
    if cadence == "weekly":
        return now.strftime("%Y-W%W")
    return now.strftime("%Y-%m-%d")


def generate_digest(
    db: sqlite3.Connection,
    user_id: int,
    period_key: str | None = None,
    cadence: str = "daily",
    force: bool = False,
) -> int:
    """Run the full digest generation pipeline. Returns the digest ID."""
    # Determine period key
    if not period_key:
        row = db.execute(
            "SELECT value FROM preferences WHERE user_id = ? AND key = 'timezone'",
            (user_id,),
        ).fetchone()
        tz_name = row["value"] if row else "UTC"
        period_key = get_period_key(cadence, tz_name)

    # Check for existing digest
    existing = db.execute(
        "SELECT id, status FROM digests WHERE user_id = ? AND cadence = ? AND period_key = ?",
        (user_id, cadence, period_key),
    ).fetchone()

    if existing and existing["status"] in ("complete", "seed") and not force:
        return existing["id"]

    # Create or update digest record
    if existing:
        digest_id = existing["id"]
        db.execute(
            "UPDATE digests SET status = 'generating' WHERE id = ?", (digest_id,)
        )
    else:
        cur = db.execute(
            "INSERT INTO digests (user_id, cadence, period_key, status) VALUES (?, ?, ?, 'generating')",
            (user_id, cadence, period_key),
        )
        digest_id = cur.lastrowid
    db.commit()

    errors = []

    try:
        # Collect ingested newsletters for this period
        if cadence == "weekly":
            newsletters = db.execute(
                "SELECT id, raw_content, content_type, parsed_articles, parse_status "
                "FROM ingested_newsletters WHERE user_id = ? AND ingested_week = ?",
                (user_id, period_key),
            ).fetchall()
        else:
            newsletters = db.execute(
                "SELECT id, raw_content, content_type, parsed_articles, parse_status "
                "FROM ingested_newsletters WHERE user_id = ? AND ingested_date = ?",
                (user_id, period_key),
            ).fetchall()

        # Parse any unparsed newsletters
        all_articles = []
        newsletter_ids = []
        for nl in newsletters:
            newsletter_ids.append(nl["id"])
            if nl["parse_status"] == "parsed" and nl["parsed_articles"]:
                all_articles.extend(json.loads(nl["parsed_articles"]))
            elif nl["parse_status"] in ("pending", "failed"):
                try:
                    articles = parse_newsletter(nl["raw_content"], nl["content_type"])
                    db.execute(
                        "UPDATE ingested_newsletters SET parsed_articles = ?, parse_status = 'parsed' WHERE id = ?",
                        (json.dumps(articles), nl["id"]),
                    )
                    all_articles.extend(articles)
                except Exception as e:
                    errors.append(f"Parse failed for newsletter {nl['id']}: {e}")
                    db.execute(
                        "UPDATE ingested_newsletters SET parse_status = 'failed', parse_error = ? WHERE id = ?",
                        (str(e), nl["id"]),
                    )

        db.commit()

        # Try LLM synthesis
        llm = get_llm_service()
        if llm.available and all_articles:
            stories, quiz = _llm_pipeline(llm, all_articles, period_key, cadence, errors)
        elif all_articles:
            # No LLM key but have articles — use seed data as fallback
            errors.append("No API key configured, using seed data")
            stories = SEED_STORIES
            quiz = SEED_QUIZ
        else:
            # No articles ingested — use seed data
            stories = SEED_STORIES
            quiz = SEED_QUIZ
            status = "seed"
            db.execute(
                "UPDATE digests SET status = ?, stories_json = ?, quiz_json = ?, "
                "story_count = ?, error_log = ?, source_newsletter_ids = ?, "
                "completed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                (
                    status,
                    json.dumps(stories),
                    json.dumps(quiz),
                    len(stories),
                    json.dumps(errors) if errors else None,
                    json.dumps(newsletter_ids),
                    digest_id,
                ),
            )
            db.commit()
            return digest_id

        # Determine final status
        if not stories:
            status = "failed"
        elif len(stories) < 5:
            status = "partial"
        else:
            status = "complete"

        db.execute(
            "UPDATE digests SET status = ?, stories_json = ?, quiz_json = ?, "
            "story_count = ?, error_log = ?, source_newsletter_ids = ?, "
            "completed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (
                status,
                json.dumps(stories),
                json.dumps(quiz),
                len(stories),
                json.dumps(errors) if errors else None,
                json.dumps(newsletter_ids),
                digest_id,
            ),
        )
        db.commit()

    except Exception as e:
        logger.exception("Digest generation failed")
        errors.append(str(e))
        db.execute(
            "UPDATE digests SET status = 'failed', error_log = ? WHERE id = ?",
            (json.dumps(errors), digest_id),
        )
        db.commit()

    return digest_id


def _llm_pipeline(
    llm: LLMService,
    articles: list[dict],
    period_key: str,
    cadence: str,
    errors: list[str],
) -> tuple[list[dict], list[dict]]:
    """Run LLM synthesis + quiz generation. Returns (stories, quiz)."""
    articles_json = json.dumps(articles[:50], indent=1)  # Cap at 50 articles

    # Estimate tokens — truncate if too large
    est_tokens = len(articles_json) // 4
    if est_tokens > 120_000:
        articles_json = json.dumps(articles[:20], indent=1)

    period_desc = f"the {'week of ' if cadence == 'weekly' else ''}{period_key}"

    # Step 1: Synthesize stories
    stories = []
    try:
        prompt = synth_prompt.USER_TEMPLATE.format(
            source_count=len(articles),
            period_description=period_desc,
            articles_json=articles_json,
        )
        result = llm.call_structured(synth_prompt.SYSTEM, prompt, max_tokens=8192)
        stories = result.get("stories", [])

        # Validate stories
        valid_stories = []
        for s in stories:
            if (
                isinstance(s, dict)
                and s.get("headline")
                and s.get("easy")
                and s.get("medium")
                and s.get("pro")
            ):
                valid_stories.append(s)
        stories = valid_stories

    except LLMUnavailableError:
        errors.append("LLM unavailable for synthesis")
        return SEED_STORIES, SEED_QUIZ
    except Exception as e:
        errors.append(f"Synthesis failed: {e}")
        return [], []

    if not stories:
        errors.append("No valid stories produced")
        return [], []

    # Step 2: Generate quiz
    quiz = []
    try:
        stories_for_quiz = json.dumps(
            [{"rank": s.get("rank", i + 1), "headline": s["headline"], "easy": s["easy"]}
             for i, s in enumerate(stories)],
            indent=1,
        )
        prompt = quiz_prompt.USER_TEMPLATE.format(stories_json=stories_for_quiz)
        result = llm.call_structured(quiz_prompt.SYSTEM, prompt, max_tokens=4096)
        raw_questions = result.get("questions", [])

        # Validate quiz questions
        for q in raw_questions:
            if (
                isinstance(q, dict)
                and q.get("question")
                and isinstance(q.get("options"), list)
                and len(q["options"]) == 4
                and isinstance(q.get("correct_index"), int)
                and 0 <= q["correct_index"] <= 3
            ):
                quiz.append(q)

    except Exception as e:
        errors.append(f"Quiz generation failed: {e}")
        # Quiz failure is non-fatal; digest still usable

    return stories, quiz
