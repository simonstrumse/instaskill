# instaskill

Claude Code skills for downloading, analyzing, and building editorial deep dives from your Instagram saved posts.

Four skills that chain together — from syncing your saves directly from Instagram's API through NLP analysis, narrative archives, and video extraction.

## Install

```bash
claude plugins add simonstrumse/instaskill
```

## The Full Pipeline

The skills chain together in order. Each skill's output feeds the next one.

```
instagram-pipeline → instagram-analysis → instagram-deep-dive
                                        → video-analysis (optional, for reels)
```

### Step 1: Download your saved posts

```
Sync my Instagram saved posts using the instagram-pipeline skill
```

This reads your Chrome cookies and syncs every saved post from Instagram's API — captions, media, timestamps, collection tags, everything. Downloads images and videos, then runs Whisper transcription and OCR to extract text from media.

**What you get:** `saved_posts.json` with full post data + local media files + extracted text.

### Step 2: Analyze everything

```
Run the full analysis pipeline on my saved posts using the instagram-analysis skill
```

Processes your posts through 10 phases: AI vision analysis, synthesis, embeddings, UMAP projections, topic modeling, sentiment analysis, network analysis, temporal patterns, psychological profiling, and a Streamlit dashboard.

**What you get:** Embeddings, 10-20 topics, sentiment scores, network graphs, temporal patterns, psychological profile, and an interactive dashboard.

### Step 3: Build a deep dive on a collection

```
Build a deep dive on my "Cooking" collection using the instagram-deep-dive skill
```

Picks one of your saved collections and builds a full editorial archive — entity extraction, event detection, narrative framing, chronicle prose, person/account profiles, and a Convex-backed Next.js frontend. Each deep dive discovers what makes that collection unique.

**What you get:** A data journalism website with chronicles, profile pages, and exploratory analysis.

### Step 4 (optional): Extract structured data from videos

```
Analyze the videos in my "Cooking" collection using the video-analysis skill and extract recipes
```

Multi-model video pipeline for reels and clips: ffmpeg scene detection → Claude Opus frame analysis → Gemini full-video enrichment → deterministic merge. The extraction schema is customizable — recipes, tutorials, exercises, art analysis, whatever your videos contain.

**What you get:** Structured JSON per video (e.g., recipe ingredients + instructions, tutorial steps, exercise details).

## Or just use natural language

You don't need to remember skill names. Just describe what you want:

- "Download all my Instagram saved posts" → triggers `instagram-pipeline`
- "How many posts do I have? Show me my collections" → triggers `instagram-pipeline status`
- "Analyze my saved posts — topics, sentiment, the whole thing" → triggers `instagram-analysis`
- "I want to build a narrative archive from my Gaza collection" → triggers `instagram-deep-dive`
- "Extract recipes from the cooking reels" → triggers `video-analysis`
- "Download my Instagram, analyze everything, and build a deep dive on my Food collection" → chains all three skills

## Skills

| Skill | What it does | Input | Output |
|-------|-------------|-------|--------|
| `instagram-pipeline` | Sync saved posts from API, download media, Whisper + OCR | Chrome login | `saved_posts.json` + local media |
| `instagram-analysis` | Vision analysis, synthesis, embeddings, topics, sentiment, networks | `saved_posts.json` | Analysis data + Streamlit dashboard |
| `instagram-deep-dive` | Entities, events, narratives, chronicles, profiles, frontend | Analyzed posts + collection name | Convex DB + Next.js pages |
| `video-analysis` | Key frames → Opus analysis → Gemini enrichment → merge | Local video files | Structured JSON per video |

## Templates

Generalized scripts the agent reads as reference and adapts to your data. Not copy-paste — the agent customizes paths, schemas, and domain logic for your collection.

```
templates/
├── pipeline/          # 10 analysis scripts (vision → export)
├── deep-dive/         # config.py + 11 scripts (extract → convex export)
├── video/             # 4 scripts (prepare → merge)
├── convex/            # Schema + query patterns with {prefix} placeholders
└── frontend/          # 5 annotated TSX patterns (layout → person detail)
```

## Reference Docs

| Doc | What it covers |
|-----|---------------|
| [`GOTCHAS.md`](reference/GOTCHAS.md) | 20+ pitfalls from 5 collections: data types, Convex quirks, frontend traps, LLM variance |
| [`DATA_CONTRACT.md`](reference/DATA_CONTRACT.md) | 9 table types with field names, types, indexes, JSON conventions |
| [`DESIGN_SYSTEM.md`](reference/DESIGN_SYSTEM.md) | Editorial design principles: fonts, colors, spacing, component patterns |

## Requirements

- Python 3.10+ (3.12+ recommended)
- Claude Code with Max plan (subagents are free — the entire pipeline can run without API keys)
- macOS with Apple Silicon (for Whisper MLX + OCR in pipeline skill)
- ffmpeg (for video pipeline only)
- Convex account (for deep dive frontend, optional)

### What's free vs. paid

The entire pipeline works on a Max plan with zero API keys. Each skill offers an optional paid mode for faster batch processing:

| Feature | Free (Max plan) | Paid (API keys) |
|---------|----------------|-----------------|
| Sync + download posts | Free (Chrome cookies) | — |
| Vision analysis | Claude subagents | Gemini 2.0 Flash |
| Synthesis | Claude subagents | Anthropic API (Haiku) |
| Embeddings, topics, sentiment | Local models | — |
| Video frame analysis | Claude subagents | Anthropic API (Opus) |
| Video enrichment | Skip (optional) | Gemini API |
| Deep dive (entities, events, etc.) | Claude subagents | — |

## Architecture

Built from analyzing 11,323 Instagram saved posts across 5 collection deep dives (Gaza, Food, Counterculture, AI, Hundetrening). Every template has been battle-tested on real data.

**Design principles:**
- **Agentic-first:** Prefer LLM subagents over deterministic scripts. The quality ceiling is always higher.
- **Discovery over configuration:** Narrative frames, account types, and entity aliases emerge from your data — not copied from another collection.
- **Trust hierarchy:** For multi-model pipelines, establish ground truth (Opus) and additive-only enrichment (Gemini).
- **Editorial, not SaaS:** The frontend follows data journalism aesthetics (ProPublica, The Pudding), not dashboard conventions.

## Author

Simon Strumse
