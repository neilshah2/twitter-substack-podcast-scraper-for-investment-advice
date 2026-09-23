"""Substack ingestion via RSS.

Substack publishes an RSS feed at <newsletter>.substack.com/feed.
No credentials needed — feed URLs come from config/sources.yaml.

Normalized post dict: {title, author, published, url, text}
"""

from __future__ import annotations

import re

import feedparser


def _html_to_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_feed(feed_url: str, max_items: int = 10) -> list[dict]:
    """Return normalized recent items from one Substack RSS feed."""
    parsed = feedparser.parse(feed_url)
    items = []
    for entry in parsed.entries[:max_items]:
        content = ""
        if "content" in entry and entry.content:
            content = entry.content[0].get("value", "")
        elif "summary" in entry:
            content = entry.summary
        items.append(
            {
                "title": entry.get("title", ""),
                "author": entry.get("author", ""),
                "published": entry.get("published", ""),
                "url": entry.get("link", ""),
                "text": _html_to_text(content),
            }
        )
    return items


def fetch_all(feed_urls: list[str], max_items: int = 10) -> list[dict]:
    """Fetch all configured Substack feeds, tagging each item with its feed."""
    out = []
    for url in feed_urls:
        for item in fetch_feed(url, max_items=max_items):
            out.append({**item, "feed_url": url})
    return out
