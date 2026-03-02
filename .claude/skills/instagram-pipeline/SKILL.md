---
name: instagram-pipeline
description: >
  Full Instagram saved posts pipeline: sync from API, download media, extract text.
  Use when the user wants to process their Instagram saved posts — sync collections,
  download media, run Whisper audio transcription + OCR on images/video frames,
  or check pipeline status. No archive download needed — works directly from Chrome cookies.
  Handles: "sync my Instagram", "process collection X", "extract collection X",
  "instagram status", "list my collections", "run pipeline on X".
argument-hint: "[collection-name or 'status' or 'collections']"
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# Instagram Saved Posts Pipeline

End-to-end pipeline: sync saved posts from Instagram's API, download media, and extract searchable text (Whisper transcription + OCR). Works with just Chrome cookies — no archive download or separate login needed.

The pipeline code is **bundled with this skill** in the `scripts/` directory — no external package needed.

## Prerequisites

- Python 3.10+ with `venv` module
- User logged into Instagram in Chrome (cookie-based API auth)
- For extraction: macOS with Apple Silicon (for `lightning-whisper-mlx` and `ocrmac`)

## Setup

### Step 0: Locate the bundled scripts

```bash
# Find the skill's scripts directory (works for both plugin and manual installs)
SCRIPTS_DIR=$(find ~/.claude -path '*/instagram-pipeline/scripts' -type d 2>/dev/null | head -1)

# Fallback: search in common locations
if [ -z "$SCRIPTS_DIR" ]; then
    SCRIPTS_DIR=$(find ~/Claude\ Code\ Projects -path '*/instagram-pipeline/scripts' -type d 2>/dev/null | head -1)
fi

echo "Scripts: $SCRIPTS_DIR"
```

If `SCRIPTS_DIR` is empty, the skill isn't installed. Install with:
```bash
claude plugin add simonstrumse/vibelabs-skills
```

### Step 1: Create venv and install (first time only)

```bash
# Option A: Use the setup script
bash "$SCRIPTS_DIR/setup.sh"                # Core (sync + download)
bash "$SCRIPTS_DIR/setup.sh" --extract      # Core + Whisper + OCR

# Option B: Manual setup
python3 -m venv .venv
.venv/bin/pip install -e "$SCRIPTS_DIR"                               # Core
.venv/bin/pip install -r "$SCRIPTS_DIR/requirements-extract.txt"      # Extraction (optional)
```

### Step 2: Set variables

```bash
PROJECT_DIR=$(pwd)
VENV="$PROJECT_DIR/.venv/bin/python3"
DATA_FILE="$PROJECT_DIR/data/instagram/saved_posts.json"
```

Verify these exist before proceeding.

## Pipeline Overview

| Step | Command | What it does | Rate |
|------|---------|-------------|------|
| **1. Sync** | `api_bootstrap sync` | Fetches all saved posts + collection tags from API | ~260 posts/min |
| **2. Media** | `api_bootstrap sync` (default) | Downloads images/videos in parallel | 4 concurrent threads |
| **3. Extract** | `media_extractor run` | Whisper large-v3 audio + ocrmac OCR | ~2.8 posts/min |

Steps 1-2 happen together in a single `sync` command. Step 3 runs separately on downloaded media.

## Workflow

### Step 0: Parse intent

- If `$ARGUMENTS` is `status` or empty → show status only (Step 1), don't run anything
- If `$ARGUMENTS` is `collections` → list collections from API, don't run anything
- Otherwise → treat `$ARGUMENTS` as collection name and run the full pipeline (Steps 1-4)

### Step 1: Show current status

If a data file exists, show enrichment and extraction progress:

```bash
SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -c "
from socmed.config import DATA_FILES
from socmed.storage.json_store import JsonStore
from collections import Counter
store = JsonStore(DATA_FILES['instagram']['saved_posts'])
posts = store.read()
enriched = sum(1 for p in posts if p.get('source') == 'archive+api')
pending = sum(1 for p in posts if p.get('source') == 'archive')
extracted = sum(1 for p in posts if p.get('extracted_text'))
with_media = sum(1 for p in posts if any(m.get('local_path') for m in p.get('media', [])))
print(f'Total: {len(posts)}')
print(f'Enriched: {enriched} ({enriched*100//len(posts) if posts else 0}%)')
print(f'Pending enrichment: {pending}')
print(f'With local media: {with_media}')
print(f'Extracted (Whisper+OCR): {extracted}')
cols = Counter()
for p in posts:
    for c in p.get('collections', []):
        cols[c] += 1
print(f'\nCollections ({len(cols)}):')
for name, count in cols.most_common(15):
    ext = sum(1 for p in posts if c in p.get('collections',[]) and p.get('extracted_text'))
    print(f'  {name}: {count}')
"
```

If no data file exists, proceed directly to Step 2 (first-time sync).
If the user only asked for status, **stop here**.

### Step 2: Sync saved posts from API

This fetches all saved posts directly from Instagram's API. Posts arrive fully enriched — captions, author info, media URLs, timestamps, engagement counts, and collection tags. No separate enrichment step needed.

```bash
# Sync all saved posts (with media download)
PYTHONUNBUFFERED=1 SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -m socmed.platforms.instagram.api_bootstrap sync

# Or sync a specific collection only
PYTHONUNBUFFERED=1 SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -m socmed.platforms.instagram.api_bootstrap sync --collection "$ARGUMENTS"

# Metadata only (skip media download for speed)
PYTHONUNBUFFERED=1 SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -m socmed.platforms.instagram.api_bootstrap sync --no-media
```

Run as a **background task**. Monitor output:
- Lists all collections with post counts
- Shows existing posts in store (for dedup)
- Progress: `Fetched N posts (M pages)...`
- 21 posts per page, ~2s between pages, ~260 posts/min
- Zero errors is normal — this is a lightweight read-only API
- ~35-45 min for 12k posts (metadata), longer with media download
- Deduplicates by shortcode — safe to run repeatedly, only adds new posts

Wait for completion. Report the summary to the user.

**To list collections without syncing:**
```bash
SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -m socmed.platforms.instagram.api_bootstrap collections
```

**To compare API vs local store:**
```bash
SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -m socmed.platforms.instagram.api_bootstrap stats
```

### Step 3: Run extraction (if needed)

Only run if posts have local media but no `extracted_text` field. **Sync with media download must complete first** since extraction needs local files.

```bash
PYTHONUNBUFFERED=1 SOCMED_DATA_DIR="$PROJECT_DIR" $VENV -m socmed.platforms.instagram.media_extractor run --collection "$ARGUMENTS" --save-every 10
```

Run as a **background task**. Monitor output:
- `A` = audio+OCR, `a` = audio only, `T` = OCR only, `.` = no extractable content
- Rate is ~2.8 posts/min (Whisper transcription is the bottleneck)
- MallocStackLogging warnings from ffmpeg subprocesses are harmless — ignore them

Wait for completion. Report the final summary.

### Step 4: Verify results

Re-run the status snippet from Step 1 to confirm:
- All posts synced (compare with API collection counts)
- Extraction coverage (~97% typical — some posts have no media)

Report the final state to the user.

## How it works

1. **Chrome cookies** — Reads `sessionid`, `csrftoken`, etc. from Chrome's cookie database (via `browser_cookie3`). No login flow needed — if you're logged into Instagram in Chrome, it just works.

2. **Collections list** — Calls `/api/v1/collections/list/` to get collection names, IDs, and post counts. Each collection has a numeric ID (e.g., `17879393448155930`).

3. **Saved feed pagination** — Calls `/api/v1/feed/saved/posts/` with cursor-based pagination. Returns 21 posts per page. Each post includes a `saved_collection_ids` array that maps back to collection names.

4. **Pre-enriched data** — Unlike an archive download (which gives bare shortcodes), the saved feed returns full post data: caption, author, media URLs, timestamps, engagement counts. Posts go straight into the store as `source: "archive+api"`.

5. **Media download** — CDN URLs from the API response are downloaded in parallel (4 threads). Files saved to `data/media/instagram/{username}/{shortcode}_{hash}.{ext}`.

6. **Text extraction** — Whisper large-v3 transcribes video audio, ocrmac OCR reads text from video frames and images. Results stored in `extracted_text` field per post.

## Operational notes

- **Idempotent** — Sync deduplicates by shortcode. Run it daily/weekly to catch new saved posts.
- **Concurrent safety** — Extraction uses `JsonStore.patch_items()` with file locking. Safe to run while sync is updating.
- **Resumable** — All steps skip already-processed items. Safe to interrupt (Ctrl+C) and restart.
- **Sleep-safe** — macOS pauses background processes during sleep; they resume automatically.
- **Always use PYTHONUNBUFFERED=1** for background tasks so output streams in real-time.
- **Data directory** — Set `SOCMED_DATA_DIR` to control where data is stored. Defaults to current working directory.

## Troubleshooting

### "No module named 'socmed'"
The virtual environment doesn't have the bundled package installed. Run setup:
```bash
SCRIPTS_DIR=$(find ~/.claude -path '*/instagram-pipeline/scripts' -type d 2>/dev/null | head -1)
.venv/bin/pip install -e "$SCRIPTS_DIR"
```

### Sync returns no posts
User needs to be logged into Instagram in Chrome. Have them open instagram.com, verify they're logged in, then retry.

### "useragent mismatch" errors
Some Instagram API endpoints are strict about User-Agent. The sync endpoint (`/api/v1/feed/saved/posts/`) does not have this issue. If you see this, you may be calling the wrong endpoint.

### Extraction seems stuck
A corrupted video file can hang ffmpeg. Kill the process — the pipeline resumes from the last save point (every 10 posts).

### Need to re-download media
Media CDN URLs expire. Run sync again — it will re-fetch fresh URLs and download missing media files.

### browser_cookie3 fails on macOS
Grant Terminal (or your IDE) "Full Disk Access" in System Settings > Privacy & Security > Full Disk Access. Chrome's cookie database is in a protected directory.
