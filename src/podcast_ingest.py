"""Podcast ingestion: RSS discovery + audio transcription.

Pulls the latest episode from each configured podcast RSS feed, downloads
its audio, and transcribes it via a Whisper-compatible transcription API
whose key comes from the TRANSCRIPTION_API_KEY environment variable.
Provider-agnostic: the HTTP call follows OpenAI's /v1/audio/transcriptions
shape, which most hosted Whisper endpoints accept.

Normalized episode dict: {podcast, episode_title, published, url, transcript}
"""

from __future__ import annotations

import os
import tempfile

import feedparser
import requests


class EnvError(RuntimeError):
    """Raised when a required environment variable is missing."""


def transcription_key() -> str:
    key = os.environ.get("TRANSCRIPTION_API_KEY")
    if not key:
        raise EnvError(
            "TRANSCRIPTION_API_KEY is not set. Export your transcription "
            "provider key, e.g. export TRANSCRIPTION_API_KEY=..."
        )
    return key


def latest_episode(feed_url: str) -> dict:
    """Return metadata for the most recent episode in a podcast RSS feed."""
    parsed = feedparser.parse(feed_url)
    if not parsed.entries:
        raise ValueError(f"No episodes found in feed: {feed_url}")
    entry = parsed.entries[0]
    audio_url = ""
    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("audio"):
            audio_url = enclosure.get("href", "")
            break
    if not audio_url:
        # Fall back to any link that looks like an audio file.
        for link in entry.get("links", []):
            if link.get("href", "").endswith((".mp3", ".m4a", ".wav")):
                audio_url = link["href"]
                break
    return {
        "podcast": parsed.feed.get("title", ""),
        "episode_title": entry.get("title", ""),
        "published": entry.get("published", ""),
        "url": entry.get("link", ""),
        "audio_url": audio_url,
    }


def transcribe(audio_url: str) -> str:
    """Download audio and transcribe it. Returns the transcript text."""
    key = transcription_key()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp:
        with requests.get(audio_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                tmp.write(chunk)
        tmp.flush()
        endpoint = os.environ.get(
            "TRANSCRIPTION_ENDPOINT", "https://api.openai.com/v1/audio/transcriptions"
        )
        with open(tmp.name, "rb") as f:
            resp = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (tmp.name, f, "audio/mpeg")},
                data={"model": os.environ.get("TRANSCRIPTION_MODEL", "whisper-1")},
                timeout=600,
            )
        resp.raise_for_status()
        return resp.json().get("text", "")


def fetch_all(feed_urls: list[str]) -> list[dict]:
    """Fetch and transcribe the latest episode of each configured feed."""
    episodes = []
    for url in feed_urls:
        meta = latest_episode(url)
        meta["transcript"] = transcribe(meta["audio_url"]) if meta["audio_url"] else ""
        episodes.append(meta)
    return episodes
