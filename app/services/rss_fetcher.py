"""RSS feed fetcher — pulls entries from RSS/Atom feeds using stdlib only."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import xml.etree.ElementTree as ET
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

USER_AGENT = "NekoNews/0.1"
FETCH_TIMEOUT = 15
ENTRY_BODY_MAX = 5000
DEDUP_TTL_DAYS = 7

# Namespace map for Atom feeds
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _strip_html(html: str) -> str:
    """Rough HTML tag stripper for feed content."""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _parse_feed(xml_bytes: bytes) -> list[dict]:
    """Parse RSS 2.0 or Atom feed XML into a list of entries.

    Each entry: {"title": str, "link": str, "body": str}.
    """
    entries = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return entries

    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag == "rss":
        # RSS 2.0
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            # Prefer content:encoded, fall back to description
            body = ""
            content_el = item.find("content:encoded", NS)
            if content_el is not None and content_el.text:
                body = content_el.text
            else:
                desc = item.findtext("description") or ""
                body = desc
            entries.append({
                "title": title[:200],
                "link": link,
                "body": _strip_html(body)[:ENTRY_BODY_MAX],
                "body_html": body[:ENTRY_BODY_MAX],
            })

    elif tag == "feed":
        # Atom
        ns = ""
        if "}" in root.tag:
            ns = root.tag.split("}")[0] + "}"
        for entry in root.findall(f"{ns}entry"):
            title = (entry.findtext(f"{ns}title") or "").strip()
            link = ""
            for link_el in entry.findall(f"{ns}link"):
                href = link_el.get("href", "")
                rel = link_el.get("rel", "alternate")
                if rel == "alternate" or not link:
                    link = href
            # Content
            body = ""
            content_el = entry.find(f"{ns}content")
            if content_el is not None and content_el.text:
                body = content_el.text
            else:
                summary_el = entry.find(f"{ns}summary")
                if summary_el is not None and summary_el.text:
                    body = summary_el.text
            entries.append({
                "title": title[:200],
                "link": link,
                "body": _strip_html(body)[:ENTRY_BODY_MAX],
                "body_html": body[:ENTRY_BODY_MAX],
            })

    return entries


def clear_seen_articles(db: sqlite3.Connection, user_id: int) -> int:
    """Delete all RSS-sourced ingested articles for user's active sources.

    Returns the number of rows deleted.
    """
    cur = db.execute(
        "DELETE FROM ingested_newsletters "
        "WHERE user_id = ? AND entry_url IS NOT NULL AND source_id IN "
        "(SELECT id FROM sources WHERE user_id = ? AND source_type = 'rss' AND active = 1)",
        (user_id, user_id),
    )
    db.commit()
    return cur.rowcount


def fetch_rss_source(
    db: sqlite3.Connection,
    user_id: int,
    source_id: int,
    feed_url: str,
) -> dict[str, Any]:
    """Fetch a single RSS feed and ingest new entries.

    Returns {"new": int, "skipped": int, "error": str|None}.
    """
    result: dict[str, Any] = {"new": 0, "skipped": 0, "error": None}

    try:
        # TTL: expire entries older than 7 days so they can be re-ingested
        db.execute(
            "DELETE FROM ingested_newsletters "
            "WHERE user_id = ? AND source_id = ? AND entry_url IS NOT NULL "
            "AND ingested_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)",
            (user_id, source_id, f"-{DEDUP_TTL_DAYS} days"),
        )
        db.commit()

        req = Request(feed_url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            xml_bytes = resp.read()

        entries = _parse_feed(xml_bytes)[:5]  # Cap at 5 most recent per feed
        if not entries:
            result["error"] = "No entries found in feed"
            return result

        for entry in entries:
            entry_url = entry.get("link")
            if not entry_url:
                continue

            # Build structured article directly from RSS fields
            article = {
                "title": entry["title"],
                "body": entry["body"],
                "url": entry_url,
            }
            parsed_json = json.dumps([article])

            raw_content = entry.get("body_html") or entry["body"]
            content_type = "html" if "<" in raw_content and ">" in raw_content else "text"

            # INSERT OR IGNORE — dedup via unique index on (user_id, entry_url)
            try:
                db.execute(
                    "INSERT INTO ingested_newsletters "
                    "(user_id, source_id, raw_content, content_type, "
                    "parsed_articles, parse_status, entry_url) "
                    "VALUES (?, ?, ?, ?, ?, 'parsed', ?)",
                    (user_id, source_id, raw_content[:ENTRY_BODY_MAX],
                     content_type, parsed_json, entry_url),
                )
                result["new"] += 1
            except sqlite3.IntegrityError:
                result["skipped"] += 1

        db.commit()

        # Update last_fetched_at
        db.execute(
            "UPDATE sources SET last_fetched_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
            "WHERE id = ?",
            (source_id,),
        )
        db.commit()

    except (URLError, TimeoutError, OSError) as e:
        result["error"] = f"Network error: {e}"
    except Exception as e:
        logger.exception("Failed to fetch RSS feed %s", feed_url)
        result["error"] = str(e)

    return result


def fetch_all_rss_sources(
    db: sqlite3.Connection,
    user_id: int,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch all active RSS sources for a user.

    If force=True, clears all seen articles first so everything is re-ingested.
    """
    if force:
        clear_seen_articles(db, user_id)

    sources = db.execute(
        "SELECT id, name, url FROM sources "
        "WHERE user_id = ? AND source_type = 'rss' AND active = 1 AND url IS NOT NULL",
        (user_id,),
    ).fetchall()

    summary: dict[str, Any] = {
        "sources_fetched": 0,
        "total_new": 0,
        "total_skipped": 0,
        "errors": [],
        "results": [],
    }

    for src in sources:
        r = fetch_rss_source(db, user_id, src["id"], src["url"])
        summary["sources_fetched"] += 1
        summary["total_new"] += r["new"]
        summary["total_skipped"] += r["skipped"]
        summary["results"].append({
            "source_id": src["id"],
            "name": src["name"],
            "url": src["url"],
            "new": r["new"],
            "skipped": r["skipped"],
            "error": r["error"],
        })
        if r["error"]:
            summary["errors"].append(f"{src['name']}: {r['error']}")

    return summary
