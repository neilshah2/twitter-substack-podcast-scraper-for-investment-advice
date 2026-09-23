# Twitter Substack Podcast Scraper for Investment Advice

A clean, de-identified framework for turning the investor's own information diet —
their X lists, their Substack feeds, their podcasts — into two artifacts every day:

1. **A written digest** of the day's most investable claims (Markdown).
2. **A spoken audio summary** (MP3) they can listen to on the commute.

You bring the sources and the API keys. The repo ships with zero real sources,
zero real accounts, and zero credentials — every example is synthetic.

## Architecture

```
 ┌────────────┐   ┌──────────────────┐   ┌──────────────┐
 │  INGEST    │   │    SUMMARIZE     │   │   EXTRACT    │
 │ x_ingest   │──▶│  summarize.py    │──▶│ extract_     │
 │ substack_  │   │  (LLM_API_KEY,   │   │ mentions.py  │
 │ ingest     │   │  investment-     │   │ (ticker      │
 │ podcast_   │   │  advice prompt)  │   │  tagging)    │
 │ ingest     │   │                  │   │              │
 └────────────┘   └──────────────────┘   └──────┬───────┘
                                                │
 ┌──────────────────────────────────────────────┤
 │  WRITE                                       │
 │  build_digest.py → output/digest-YYYY-MM-DD.md
 │  make_audio.py   → output/digest-YYYY-MM-DD.mp3
 │  extract_mentions→ output/mentions-YYYY-MM-DD.jsonl
 └──────────────────────────────────────────────┘
```

- **Ingest** normalizes every source into a common dict shape.
- **Summarize** calls an LLM (Anthropic-compatible messages interface) with a
  prompt that extracts only investable signal: key claims, tickers, bull/bear
  arguments, action items.
- **Extract** tags ticker mentions and appends them as JSONL objects matching
  `schemas/mention.schema.json` — ready for a research library.
- **Audio/write** renders the digest to Markdown and a spoken MP3.

## Setup

Requires Python 3.10+.

```bash
git clone <this-repo>
cd twitter-substack-podcast-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Declare your sources (copy, then edit — never commit real URLs)
cp config/sources.example.yaml config/sources.yaml

# 2. Provide secrets via environment (never commit these)
cp .env.example .env   # then edit, or export directly
export X_BEARER_TOKEN=...            # X API v2 bearer token
export LLM_API_KEY=...               # Anthropic-compatible LLM key
export TRANSCRIPTION_API_KEY=...     # Whisper-compatible transcription key
export TTS_API_KEY=...               # TTS provider key

# 3. Run
python3 src/build_digest.py --date 2026-09-23
python3 src/build_digest.py --date 2026-09-23 --dry-run      # text only, no audio
python3 src/build_digest.py --date 2026-09-23 --skip-audio   # write files, no MP3
python3 src/build_digest.py --date 2026-09-23 --voice narrator_female
```

### Spoken audio & voices

`make_audio.py` turns the digest into an MP3 via your TTS provider. Sample
voice presets live in `config/voices.example.yaml` — all stock synthetic
voices, no real people. Copy it to `config/voices.yaml` to customize; your
file takes precedence over the shipped example.

| preset | provider voice | description |
|---|---|---|
| `narrator_male` | `onyx` | masculine-sounding synthetic voice |
| `narrator_female` | `nova` | feminine-sounding synthetic voice |
| `narrator_neutral` | `alloy` | neutral synthetic voice (default) |

```bash
python3 src/make_audio.py --digest output/digest-2026-09-23.md --voice narrator_female
python3 src/make_audio.py --digest output/digest-2026-09-23.md --voice narrator_male --dry-run
```

`--voice` accepts a preset name or a raw provider voice id, and overrides
`TTS_VOICE`. The spoken script contains only the digest's summaries and key
claims — no personal data, no source identities.

### Config reference (`config/sources.yaml`)

```yaml
x:
  lists:
    - name: "my semiconductor list"
      list_id: "YOUR_X_LIST_ID"
  bookmarks: false            # or true, with an OAuth 2.0 user-context
                              # X_BEARER_TOKEN (bookmark.read scope) --
                              # the app-only bearer token cannot read bookmarks
substack:
  feeds:
    - "https://example-newsletter.substack.com/feed"
podcasts:
  feeds:
    - "https://example.com/podcast/feed.xml"
```

All sources in `sources.example.yaml` are placeholders (example.com / YOUR_*
values). Ingest modules raise a clear error if the required env key is missing.

## Sample output

`output/digest-YYYY-MM-DD.md` (see `samples/sample_digest.md` for a synthetic example):

```markdown
# Investment Digest — 2026-09-23

## X · @analyst_a (list: semiconductors)
**Summary:** ...
**Key claims:** ...  **Tickers:** EXSC
```

`output/mentions-YYYY-MM-DD.jsonl` — one mention object per line, validated
against `schemas/mention.schema.json` (synthetic examples in
`samples/sample_mentions.jsonl`):

```json
{"ticker":"EXSC","date":"2026-09-23","source_type":"x","source":"semiconductor list",
 "said_by":"analyst_a","text":"EXSC's new chip shows 2x perf/watt; guidance raised.",
 "url":"https://x.com/analyst_a/status/1234567890"}
```

## Disclaimer

This tool organizes and summarizes content you already follow. It is not
financial advice, and summaries are generated by an LLM — verify every claim
against the linked source before acting.
