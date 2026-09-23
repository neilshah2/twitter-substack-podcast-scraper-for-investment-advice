"""Investment-advice-focused summarization via an LLM.

Uses an Anthropic-compatible messages API, authenticated with the LLM_API_KEY
environment variable. The prompt is deliberately narrow: it extracts only
investable signal — key claims, tickers, bull/bear arguments, action items —
and contains no personal data, no subscription names, and no non-finance content.

Normalized summary dict: {summary, key_claims[], tickers[], bull_case,
bear_case, action_items[]}
"""

from __future__ import annotations

import json
import os

import requests

SYSTEM_PROMPT = """You summarize investor information feeds. For each item, output
ONLY valid JSON with these fields:
- summary: 2-3 sentence neutral summary of the item's investment content.
- key_claims: list of 1-2 sentence investable claims made in the item.
- tickers: list of stock tickers mentioned (uppercase, no $ prefix).
- bull_case: strongest bullish argument, or null.
- bear_case: strongest bearish argument, or null.
- action_items: concrete investor action items implied, or [].
Ignore non-investment content entirely. Never invent tickers or claims."""


class EnvError(RuntimeError):
    """Raised when a required environment variable is missing."""


def llm_key() -> str:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        raise EnvError(
            "LLM_API_KEY is not set. Export your LLM API key, "
            "e.g. export LLM_API_KEY=..."
        )
    return key


def summarize_item(source_label: str, text: str, max_chars: int = 12000) -> dict:
    """Summarize one ingested item into investable-signal JSON."""
    endpoint = os.environ.get(
        "LLM_ENDPOINT", "https://api.anthropic.com/v1/messages"
    )
    resp = requests.post(
        endpoint,
        headers={
            "x-api-key": llm_key(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"),
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"Source: {source_label}\n\nContent:\n{text[:max_chars]}",
                }
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json()
    # Anthropic messages response: content blocks; find the text block.
    text_out = "".join(
        b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text"
    )
    try:
        return json.loads(text_out)
    except json.JSONDecodeError:
        # Graceful fallback if the model wrapped JSON in prose.
        start, end = text_out.find("{"), text_out.rfind("}")
        return json.loads(text_out[start : end + 1])
