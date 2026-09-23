"""X (Twitter) ingestion.

Fetch recent posts from the user's X lists / bookmarks via the X API v2
bearer token, provided through the X_BEARER_TOKEN environment variable.
"Bring your own credentials": without the token, every public function
raises EnvError with a clear message instead of failing cryptically.

Normalized post dict: {id, author, text, created_at, url}
"""

from __future__ import annotations

import os

import requests

API_BASE = "https://api.twitter.com/2"
LIST_TWEETS_URL = API_BASE + "/lists/{list_id}/tweets"


class EnvError(RuntimeError):
    """Raised when a required environment variable is missing."""


def bearer_token() -> str:
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise EnvError(
            "X_BEARER_TOKEN is not set. Export your X API v2 bearer token, "
            "e.g. export X_BEARER_TOKEN=... "
        )
    return token


def _headers() -> dict:
    return {"Authorization": f"Bearer {bearer_token()}"}


def _normalize(tweet: dict, users: dict) -> dict:
    author = users.get(tweet.get("author_id", ""), {}).get("username", "unknown")
    return {
        "id": tweet.get("id"),
        "author": author,
        "text": tweet.get("text", ""),
        "created_at": tweet.get("created_at"),
        "url": f"https://x.com/{author}/status/{tweet.get('id')}",
    }


def fetch_list_posts(list_id: str, max_results: int = 50) -> list[dict]:
    """Return normalized recent posts from one X list."""
    resp = requests.get(
        LIST_TWEETS_URL.format(list_id=list_id),
        headers=_headers(),
        params={
            "max_results": max_results,
            "tweet.fields": "created_at,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}
    return [_normalize(t, users) for t in payload.get("data", [])]


def fetch_bookmarks() -> list[dict]:
    """Return normalized posts from the authenticated user's bookmarks.

    Note: requires an OAuth 2.0 user-context token with bookmark.read scope;
    the app-only bearer token cannot read bookmarks, so this is a stub that
    fails clearly until a suitable token is supplied via X_BEARER_TOKEN.
    """
    raise EnvError(
        "Bookmarks require an OAuth 2.0 user-context token (bookmark.read scope). "
        "Set X_BEARER_TOKEN to such a token, or leave bookmarks: false."
    )
