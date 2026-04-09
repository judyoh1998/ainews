"""Newsletter content parser — extracts articles from HTML or plain text."""

from __future__ import annotations

import re
from typing import Any


def parse_newsletter(raw_content: str, content_type: str) -> list[dict[str, Any]]:
    """Extract articles from newsletter content.

    Returns list of {"title": str, "body": str, "url": str|None}.
    Uses a 3-tier fallback: structured HTML -> heuristic split -> whole-document.
    """
    if not raw_content or not raw_content.strip():
        return []

    if content_type == "html":
        articles = _extract_from_html(raw_content)
        if len(articles) >= 2:
            return articles
        # Fallback: strip HTML and try text extraction
        stripped = _strip_html(raw_content)
        articles = _extract_from_text(stripped)
        if articles:
            return articles
    else:
        articles = _extract_from_text(raw_content)
        if articles:
            return articles

    # Final fallback: treat entire content as one article
    text = _strip_html(raw_content) if content_type == "html" else raw_content
    return [{"title": "Full Newsletter", "body": text.strip()[:5000], "url": None}]


def _extract_from_html(html: str) -> list[dict[str, Any]]:
    """Extract articles from HTML using heading-based segmentation."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove script/style tags
        for tag in soup(["script", "style"]):
            tag.decompose()

        articles = []
        # Look for heading + content patterns
        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            title = heading.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Collect text from siblings until next heading
            body_parts = []
            link = None
            for sib in heading.find_next_siblings():
                if sib.name in ("h1", "h2", "h3", "h4"):
                    break
                text = sib.get_text(strip=True)
                if text:
                    body_parts.append(text)
                # Grab first link
                if link is None:
                    a_tag = sib.find("a", href=True)
                    if a_tag:
                        link = a_tag["href"]

            body = " ".join(body_parts)
            if body:
                articles.append({"title": title, "body": body[:3000], "url": link})

        return articles
    except Exception:
        return []


def _extract_from_text(text: str) -> list[dict[str, Any]]:
    """Extract articles from plain text using heuristic splitting."""
    articles = []

    # Try splitting on common newsletter separators
    separators = [
        r"\n---+\n",       # --- dividers
        r"\n\*\*\*+\n",    # *** dividers
        r"\n#{1,4}\s+",    # Markdown headings
        r"\n\d+\.\s+",     # Numbered lists
    ]

    segments = None
    for sep in separators:
        parts = re.split(sep, text)
        if len(parts) >= 3:
            segments = parts
            break

    if segments is None:
        # Try splitting on double newlines for paragraph-based extraction
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) >= 3:
            segments = paragraphs

    if segments:
        for seg in segments:
            seg = seg.strip()
            if len(seg) < 20:
                continue
            lines = seg.split("\n", 1)
            title = lines[0].strip()[:200]
            body = lines[1].strip()[:3000] if len(lines) > 1 else seg[:3000]
            articles.append({"title": title, "body": body, "url": None})

    return articles


def _strip_html(html: str) -> str:
    """Remove HTML tags, returning plain text."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
