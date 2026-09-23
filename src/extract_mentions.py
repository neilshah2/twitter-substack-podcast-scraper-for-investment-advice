"""Ticker tagging for digest summaries.

Tags $TICKER cashtags and bare tickers against a small built-in ticker list,
then merges tickers already reported by the summarizer. Produces mention
objects matching schemas/mention.schema.json and appends them as JSONL.

Mention: {ticker, date, source_type, source, said_by, text, url, episode?}
"""

from __future__ import annotations

import json
import os
import re

# Small built-in list of recognizable tickers (synthetic examples included).
# Extend via the TICKER_LIST env var: comma-separated uppercase tickers.
BUILT_IN_TICKERS = {
    "AAPL", "MSFT", "NVDA", "AMD", "TSM", "AVGO", "MU", "AMAT", "LRCX",
    "META", "GOOGL", "AMZN", "JPM", "XOM", "LLY", "UNH",
    # Synthetic tickers used only in samples/tests.
    "EXSC", "GRNP", "CLOU",
}

CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})\b")
BARE_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")


def ticker_universe() -> set[str]:
    extra = os.environ.get("TICKER_LIST", "")
    return BUILT_IN_TICKERS | {t.strip().upper() for t in extra.split(",") if t.strip()}


def tag_tickers(text: str, known: set[str] | None = None) -> list[str]:
    """Return sorted uppercase tickers found in text."""
    universe = known or ticker_universe()
    found = {m.group(1) for m in CASHTAG_RE.finditer(text)} & universe
    found |= {m.group(1) for m in BARE_TICKER_RE.finditer(text)} & universe
    return sorted(found)


def make_mention(
    *,
    ticker: str,
    date: str,
    source_type: str,
    source: str,
    said_by: str,
    text: str,
    url: str,
    episode: str | None = None,
) -> dict:
    mention = {
        "ticker": ticker.upper().lstrip("$"),
        "date": date,
        "source_type": source_type,
        "source": source,
        "said_by": said_by,
        "text": text,
        "url": url,
    }
    if episode:
        mention["episode"] = episode
    return mention


def extract_from_item(
    summary: dict, *, date: str, source_type: str, source: str,
    said_by: str, url: str, episode: str | None = None,
) -> list[dict]:
    """Build mention objects from one summarized item."""
    corpus = " ".join(
        [summary.get("summary", "")]
        + summary.get("key_claims", [])
        + summary.get("tickers", [])
    )
    tickers = tag_tickers(corpus) or [t.upper() for t in summary.get("tickers", [])]
    mentions = []
    for ticker in tickers:
        claims = [c for c in summary.get("key_claims", []) if ticker in c.upper()]
        text = claims[0] if claims else summary.get("summary", "")
        if len(text) > 300:
            text = text[:297] + "..."
        mentions.append(
            make_mention(
                ticker=ticker, date=date, source_type=source_type,
                source=source, said_by=said_by, text=text, url=url,
                episode=episode,
            )
        )
    return mentions


def append_jsonl(path: str, mentions: list[dict]) -> None:
    """Append mention objects to a JSONL file (creating parent dirs)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for m in mentions:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
