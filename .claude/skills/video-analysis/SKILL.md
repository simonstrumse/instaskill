# Video Analysis Skill

Analyze video content (reels, clips) from Instagram saved posts using key frame extraction and multi-modal AI models.

## Trigger Keywords

- "analyze videos", "watch videos", "video analysis", "watch reels"
- "key frames", "extract from video", "video recipe"
- "what's in the videos", "video content"

## Prerequisites

- **ffmpeg** installed (`brew install ffmpeg`)
- **Python venv** at `.venv/` with dependencies
- **Local video files** downloaded (typically in `data/{collection}/videos/`)
- **API keys** in `.env`: `GOOGLE_API_KEY` (for Gemini enrichment, optional)

## Overview

The video analysis pipeline has 5 phases. Each phase is independent — you can start from any phase if prior outputs exist.

**Templates:** `templates/video/video_prepare.py`, `video_analyze.py`, `video_enrich.py`, `video_merge.py`

## Phase 1: Prepare Key Frames

**Template:** `templates/video/video_prepare.py`

Extract representative frames from each video using ffmpeg scene detection.

```bash
python3 video_prepare.py --frames 16 --video-dir data/{collection}/videos
```

**Parameters:**
- `--frames 8|16|24` — frames per video (default 16). Use 8 for simple content, 24 for complex multi-step content
- `--limit N` — only process first N videos
- `--video-dir PATH` — directory containing video files
- Output: `data/{collection}/video_frames/{postId}/frame_*.jpg`

**How it works:**
- Uses ffmpeg scene detection (`select='gt(scene,0.3)'`) to find visually distinct moments
- Falls back to uniform sampling if scene detection yields too few frames
- Generates a batch manifest for Phase 2

## Phase 2: Analyze with AI (Subagents)

**Template:** `templates/video/video_analyze.py`

Launch Claude subagents to analyze batches of video frames with structured JSON output.

```bash
python3 video_analyze.py --model opus --batch-size 6 --schema schema.json
```

**Parameters:**
- `--model opus|sonnet` — which Claude model (default opus). Opus is more accurate; Sonnet is faster for simpler analysis
- `--batch-size N` — posts per batch (default 6). Larger = fewer API calls but longer context
- `--limit N` — only process first N posts
- `--schema PATH` — JSON schema for extraction output (customize per domain)

**Subagent prompt template** produces per-post JSON. The schema is customizable — here's a recipe example:
```json
{
  "postId": "string",
  "isRecipe": true,
  "title": "string",
  "slug": "string",
  "description": "string",
  "videoSummary": "string — literal description of what happens in the video",
  "videoOnlyInsights": ["things ONLY visible in video, not in any text"],
  "confidence": "high|medium|low",
  "ingredients": [{"amount": "", "item": "", "note": ""}],
  "instructions": [{"step": 1, "text": ""}]
}
```

For non-recipe domains, replace the schema fields. Examples:
- **Art analysis:** `medium`, `technique`, `style`, `colorPalette`, `composition`
- **Tutorial:** `tool`, `steps`, `prerequisites`, `difficulty`, `duration`
- **Exercise:** `exercise`, `sets`, `reps`, `muscleGroup`, `equipment`

**Output:** `data/{collection}/video_extracted.json`

## Phase 3: Merge Batch Results

Combine results from multiple batch runs, deduplicating by postId. Handled by `video_analyze.py merge` command or as a step in the analyze script.

## Phase 4: Gemini Enrichment (Optional)

**Template:** `templates/video/video_enrich.py`

Send full videos to Gemini 2.0 Flash for comparison against Opus results. Gemini watches the complete video (not just key frames) and reports what Opus missed.

```bash
python3 video_enrich.py --delay 5 --video-dir data/{collection}/videos
```

**Parameters:**
- `--delay N` — seconds between API calls (default 5, for rate limiting)
- `--limit N` — only process first N videos

**Output per post:**
```json
{
  "postId": "string",
  "missedIngredients": ["string"],
  "missedTechniques": ["string"],
  "missedOnScreenText": ["string"],
  "corrections": ["string"],
  "audioInsights": ["string"],
  "motionInsights": ["string"],
  "overallAddedValue": "high|medium|low|none"
}
```

**Important:** Gemini hallucinates confidently. Its output is NEVER treated as ground truth — only as additive supplements to Opus findings.

## Phase 5: Finalize

**Template:** `templates/video/video_merge.py`

Merge all sources into one authoritative file and export.

```bash
python3 video_merge.py                    # merge + export
python3 video_merge.py --dry              # preview only
python3 video_merge.py stats              # show counts
```

**Ground truth principle:** Opus is always ground truth. Gemini only adds — never overrides.

- Opus fields are NEVER overridden by Gemini
- Gemini missed items are appended (deduplicated, tagged `video-only`)
- Gemini corrections are stored as informational tips, NOT applied as data changes
- Gemini missed techniques go to tips, NOT injected into instructions

**Outputs:**
- Merged data file with all sources combined
- JSONL export for database import
- QA report showing before/after changes

## Trust Hierarchy

This is the most important design principle:

| Source | Role | Can override? |
|--------|------|--------------|
| Claude Opus (16 frames) | **Ground truth** | N/A — authoritative |
| Claude Sonnet (16 frames) | Backup analyzer | Only if Opus unavailable |
| Gemini Flash (full video) | **Additive enrichment** | Never overrides Opus |
| Deterministic merge script | Combines all sources | Rules-based, no LLM interpretation |

The merge step is always a **deterministic script**, not an LLM call. No interpretation, just rules.

## Adapting for Other Domains

1. **Download videos** to `data/{collection}/videos/`
2. **Define your extraction schema** (replace recipe fields with domain-specific fields)
3. **Customize the subagent prompt** in `video_analyze.py`
4. **Run phases 1-5** with collection-specific paths
5. **Update database schema** for any new fields

## Requirements

```
anthropic          # Claude API (for subagents)
google-generativeai # Gemini API (Phase 4 only)
Pillow             # Image processing for key frames
```

Plus `ffmpeg` installed on the system.

## File Reference (templates)

| Template | Purpose |
|----------|---------|
| `templates/video/video_prepare.py` | Phase 1: ffmpeg scene detection → key frames |
| `templates/video/video_analyze.py` | Phases 2-3: Opus subagent batch analysis + merge |
| `templates/video/video_enrich.py` | Phase 4: Gemini full-video enrichment |
| `templates/video/video_merge.py` | Phase 5: Deterministic merge + trust hierarchy + QA |
