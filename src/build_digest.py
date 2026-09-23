"""Orchestrator CLI: ingest -> summarize -> extract -> audio/write.

Usage:
    python3 src/build_digest.py --date 2026-09-23
    python3 src/build_digest.py --date 2026-09-23 --dry-run       # text only, no audio
    python3 src/build_digest.py --date 2026-09-23 --skip-audio
    python3 src/build_digest.py --date 2026-09-23 --voice narrator_female

Writes:
    output/digest-YYYY-MM-DD.md
    output/digest-YYYY-MM-DD.mp3   (unless --dry-run / --skip-audio)
    output/mentions-YYYY-MM-DD.jsonl
    output/manifest-YYYY-MM-DD.json  (matches schemas/digest.schema.json)
"""

from __future__ import annotations

import argparse
import json
import os

import yaml

from extract_mentions import append_jsonl, extract_from_item
from make_audio import digest_to_script, resolve_voice, synthesize
from podcast_ingest import fetch_all as fetch_podcasts
from substack_ingest import fetch_all as fetch_substack
from summarize import summarize_item
from x_ingest import fetch_bookmarks, fetch_list_posts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_sources(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_placeholder(value: str) -> bool:
    return "YOUR_" in value or "example.com" in value or "example-newsletter" in value


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the daily investment digest.")
    ap.add_argument("--date", required=True, help="Digest date, YYYY-MM-DD.")
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "sources.yaml"),
                    help="Path to sources.yaml.")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "output"))
    ap.add_argument("--dry-run", action="store_true",
                    help="Run ingest+summarize, print script, skip audio + writes.")
    ap.add_argument("--skip-audio", action="store_true", help="Skip MP3 generation.")
    ap.add_argument(
        "--voice",
        help="Voice preset (narrator_male, narrator_female, narrator_neutral) "
             "or raw provider voice id for the MP3. Overrides TTS_VOICE.",
    )
    args = ap.parse_args()

    sources = load_sources(args.config)
    date = args.date
    os.makedirs(args.outdir, exist_ok=True)

    items: list[dict] = []  # manifest items
    mentions: list[dict] = []
    md_sections: list[str] = [f"# Investment Digest — {date}\n"]

    # --- X ---
    for lst in sources.get("x", {}).get("lists", []):
        if is_placeholder(lst.get("list_id", "")):
            print(f"Skipping placeholder X list: {lst.get('name')}")
            continue
        for post in fetch_list_posts(lst["list_id"]):
            s = summarize_item(f"x list '{lst['name']}' by @{post['author']}", post["text"])
            items.append({"source_type": "x", "source": lst["name"], **s})
            mentions += extract_from_item(
                s, date=date, source_type="x", source=lst["name"],
                said_by=post["author"], url=post["url"],
            )
            md_sections.append(render_item("X", f"@{post['author']}", post["url"], s))

    if sources.get("x", {}).get("bookmarks"):
        for post in fetch_bookmarks():
            s = summarize_item("x bookmarks", post["text"])
            items.append({"source_type": "x", "source": "bookmarks", **s})
            mentions += extract_from_item(
                s, date=date, source_type="x", source="bookmarks",
                said_by=post["author"], url=post["url"],
            )
            md_sections.append(render_item("X", f"@{post['author']}", post["url"], s))

    # --- Substack ---
    feeds = [u for u in sources.get("substack", {}).get("feeds", []) if not is_placeholder(u)]
    for item in fetch_substack(feeds):
        s = summarize_item(f"substack '{item['title']}'", item["text"])
        items.append({"source_type": "substack", "source": item["title"], **s})
        mentions += extract_from_item(
            s, date=date, source_type="substack", source=item["title"],
            said_by=item["author"], url=item["url"],
        )
        md_sections.append(render_item("Substack", item["title"], item["url"], s))

    # --- Podcasts ---
    pfeeds = [u for u in sources.get("podcasts", {}).get("feeds", []) if not is_placeholder(u)]
    for ep in fetch_podcasts(pfeeds):
        s = summarize_item(f"podcast '{ep['episode_title']}'", ep["transcript"])
        items.append({"source_type": "podcast", "source": ep["podcast"], **s})
        mentions += extract_from_item(
            s, date=date, source_type="podcast", source=ep["podcast"],
            said_by=ep["podcast"], url=ep["url"], episode=ep["episode_title"],
        )
        md_sections.append(render_item("Podcast", ep["episode_title"], ep["url"], s))

    digest_md = "\n".join(md_sections) + "\n"
    md_path = os.path.join(args.outdir, f"digest-{date}.md")
    mentions_path = os.path.join(args.outdir, f"mentions-{date}.jsonl")
    audio_path = os.path.join(args.outdir, f"digest-{date}.mp3")
    manifest_path = os.path.join(args.outdir, f"manifest-{date}.json")

    if args.dry_run:
        print(digest_md)
        print("\n--- spoken script ---\n")
        print(digest_to_script(digest_md))
        print(f"\n(dry run: would append {len(mentions)} mentions)")
        return

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(digest_md)
    append_jsonl(mentions_path, mentions)
    manifest = {
        "date": date,
        "sources": [i["source"] for i in items],
        "items": [
            {
                "source_type": i["source_type"],
                "source": i["source"],
                "summary": i["summary"],
                "key_claims": i["key_claims"],
                "tickers": i["tickers"],
            }
            for i in items
        ],
        "audio_file": os.path.basename(audio_path),
        "mentions_file": os.path.basename(mentions_path),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if not args.skip_audio:
        voice = resolve_voice(args.voice)
        synthesize(digest_to_script(digest_md), audio_path, voice)
        print(f"Wrote {audio_path} (voice: {voice})")

    print(f"Wrote {md_path}")
    print(f"Wrote {mentions_path} ({len(mentions)} mentions)")
    print(f"Wrote {manifest_path}")


def render_item(kind: str, title: str, url: str, s: dict) -> str:
    claims = "\n".join(f"- {c}" for c in s.get("key_claims", []))
    actions = "\n".join(f"- {a}" for a in s.get("action_items", []))
    tickers = ", ".join(s.get("tickers", [])) or "none"
    return (
        f"## {kind} · {title}\n"
        f"[source]({url})\n\n"
        f"**Summary:** {s.get('summary', '')}\n\n"
        f"**Key claims:**\n{claims or '—'}\n\n"
        f"**Tickers:** {tickers}\n\n"
        f"**Bull case:** {s.get('bull_case') or '—'}\n\n"
        f"**Bear case:** {s.get('bear_case') or '—'}\n\n"
        f"**Action items:**\n{actions or '—'}\n"
    )


if __name__ == "__main__":
    main()
