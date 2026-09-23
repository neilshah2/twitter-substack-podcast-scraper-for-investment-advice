"""Spoken audio summary of the digest (MP3).

Uses a TTS provider authenticated with the TTS_API_KEY environment variable.
The script text is derived only from the digest's summaries and key claims —
no personal data, no subscription names are spoken.

Usage:
    python3 src/make_audio.py --digest output/digest-2026-09-23.md \
        --out output/digest-2026-09-23.mp3
    python3 src/make_audio.py --digest output/digest-2026-09-23.md --dry-run
    python3 src/make_audio.py --digest output/digest-2026-09-23.md \
        --voice narrator_female --dry-run

Voices: --voice takes a preset (narrator_male, narrator_female,
narrator_neutral) resolved from config/voices.yaml, falling back to
config/voices.example.yaml, or a raw provider voice id; it overrides
the TTS_VOICE environment variable.
"""

from __future__ import annotations

import argparse
import os
import re

import requests

try:
    import yaml
except ImportError:  # voices presets are optional; PyYAML is in requirements
    yaml = None


class EnvError(RuntimeError):
    """Raised when a required environment variable is missing."""


def tts_key() -> str:
    key = os.environ.get("TTS_API_KEY")
    if not key:
        raise EnvError(
            "TTS_API_KEY is not set. Export your TTS provider key, "
            "e.g. export TTS_API_KEY=..."
        )
    return key


def digest_to_script(markdown: str, max_chars: int = 8000) -> str:
    """Turn a digest Markdown file into a speakable script.

    Strips Markdown formatting and truncates to a length that keeps the
    audio summary to a few minutes.
    """
    text = re.sub(r"[#*_>`\[\]()-]", " ", markdown)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "."
    return "Here is your investment digest. " + text


def _config_dir() -> str:
    """Absolute path to the repo's config/ dir, regardless of cwd."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config")


def resolve_voice(name: str) -> str:
    """Map a --voice value to a provider voice id.

    Accepts a preset (e.g. narrator_female) or a raw provider voice id
    passed through unchanged. Presets resolve from the user's
    config/voices.yaml first, falling back to config/voices.example.yaml;
    a preset missing from both is treated as a raw voice id.
    """
    if not name:
        return os.environ.get("TTS_VOICE", "alloy")
    if yaml:
        for cfg_path in (os.path.join(_config_dir(), "voices.yaml"),
                         os.path.join(_config_dir(), "voices.example.yaml")):
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8") as f:
                    presets = (yaml.safe_load(f) or {}).get("voices", {})
                if name in presets:
                    return presets[name]["provider_voice"]
    return name


def synthesize(script: str, out_path: str, voice: str) -> None:
    """Synthesize speech and write an MP3 file."""
    endpoint = os.environ.get("TTS_ENDPOINT", "https://api.openai.com/v1/audio/speech")
    resp = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {tts_key()}"},
        json={
            "model": os.environ.get("TTS_MODEL", "tts-1"),
            "voice": voice,
            "input": script,
            "response_format": "mp3",
        },
        timeout=300,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate spoken MP3 digest.")
    ap.add_argument("--digest", required=True, help="Path to digest Markdown file.")
    ap.add_argument("--out", help="Output MP3 path (default: digest path with .mp3).")
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print the spoken script without calling the TTS API.",
    )
    ap.add_argument(
        "--voice",
        help="Voice preset (narrator_male, narrator_female, narrator_neutral) "
             "or a raw provider voice id. Overrides TTS_VOICE.",
    )
    args = ap.parse_args()

    with open(args.digest, encoding="utf-8") as f:
        script = digest_to_script(f.read())

    voice = resolve_voice(args.voice)

    if args.dry_run:
        print(f"[voice: {voice}]")
        print(script)
        return

    out = args.out or os.path.splitext(args.digest)[0] + ".mp3"
    synthesize(script, out, voice)
    print(f"Wrote {out} (voice: {voice})")


if __name__ == "__main__":
    main()
