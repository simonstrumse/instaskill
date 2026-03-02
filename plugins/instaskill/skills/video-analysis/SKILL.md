---
name: video-analysis
description: >
  Extract structured data from videos: key frames, Opus analysis, Gemini enrichment,
  deterministic merge. For recipes, tutorials, exercises from Instagram reels.
---

# Video Analysis Skill

Analyze video content (reels, clips) from Instagram saved posts using key frame extraction and multi-modal AI models.

## Trigger Keywords

- "analyze videos", "watch videos", "video analysis", "watch reels"
- "key frames", "extract from video", "video recipe"
- "what's in the videos", "video content"

## Prerequisites

- **Prior skill:** Run `instagram-pipeline` first to download media files
- **ffmpeg** installed (`brew install ffmpeg`)
- **Python venv** at `.venv/` with dependencies: `pip install -r templates/video/requirements.txt`
- **Local video files** — downloaded by `instagram-pipeline` to `data/media/instagram/{username}/`. Filter video files (`.mp4`) from this directory into `data/{collection}/videos/` or point `--video-dir` at the media directory directly.
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

## Phase 2: Analyze with AI

**Template:** `templates/video/video_analyze.py`

Analyze batches of video frames with Claude vision for structured extraction.

**Two modes — ask the user which they prefer:**

| Mode | Cost | Speed | How it works |
|------|------|-------|-------------|
| `--mode subagent` (default) | **Free** on Max plan | Agent-driven loop | Generates prompt + frame files → agent feeds to subagents |
| `--mode api` | **Paid** (Anthropic API key) | Automated batch | Direct API calls with base64 images |

```bash
# Free (default) — generates prompts for the agent to feed to subagents
python3 video_analyze.py analyze

# Paid — direct API calls
ANTHROPIC_API_KEY=sk-... python3 video_analyze.py analyze --mode api --model opus
```

**Parameters:**
- `--mode subagent|api` — free subagent prompts or paid direct API (default: subagent)
- `--model opus|sonnet` — which Claude model for API mode (default opus). Opus is more accurate; Sonnet is faster
- `--batch-size N` — posts per batch (default 6). Larger = fewer calls but longer context
- `--limit N` — only process first N posts

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

## Phase 4: Gemini Enrichment (Optional, Paid)

**Template:** `templates/video/video_enrich.py`

**This phase is entirely optional.** It requires a Google API key and costs money. Skip it if you want a free-only pipeline — Phase 2 with Claude subagents is sufficient for most use cases.

Send full videos to Gemini 2.0 Flash for comparison against Claude results. Gemini watches the complete video (not just key frames) and reports what Claude missed.

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
ffmpeg             # System binary (brew install ffmpeg)
```

**If using API mode (paid):**
```
anthropic          # Claude API (Phase 2 --mode api only)
```

**If using Gemini enrichment (optional, paid):**
```
google-generativeai # Gemini API (Phase 4 only)
```

No external packages needed for subagent mode — just ffmpeg and Claude Code with Max plan.

## File Reference (templates)

| Template | Purpose |
|----------|---------|
| `templates/video/video_prepare.py` | Phase 1: ffmpeg scene detection → key frames |
| `templates/video/video_analyze.py` | Phases 2-3: Opus subagent batch analysis + merge |
| `templates/video/video_enrich.py` | Phase 4: Gemini full-video enrichment |
| `templates/video/video_merge.py` | Phase 5: Deterministic merge + trust hierarchy + QA |
