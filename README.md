# instaskill

Claude Code skills + reusable templates for analyzing Instagram saved posts collections.

Four skills that cover the entire Instagram saved posts workflow — from syncing posts directly from Instagram's API through analysis, editorial deep dives, and video extraction.

## Quick Start

### 1. Install the skills

```bash
# Add as a Claude Code plugin
claude plugins add simonstrumse/instaskill
```

### 2. Sync your saved posts from Instagram

```
/instagram-pipeline
```

Syncs saved posts directly from Instagram's API using Chrome cookies — no archive download needed. Downloads media and extracts text (Whisper transcription + OCR). ~260 posts/min.

### 3. Run the base analysis pipeline

```
/instagram-analysis
```

Processes your `saved_posts.json` through 10 phases: synthesis → embeddings → UMAP → topics → sentiment → networks → temporal → psychological profile → export → dashboard.

### 4. Build a deep dive on a collection

```
/instagram-deep-dive
```

Takes a single saved collection (e.g., "Climate", "Music", "Cooking") and builds a full editorial archive: entity extraction, event detection, narrative framing, chronicle prose, person/account profiles, and Convex-backed frontend.

### 5. Extract structured data from videos

```
/video-analysis
```

Multi-model video pipeline: ffmpeg scene detection → Claude Opus frame analysis → Gemini full-video enrichment → deterministic merge with trust hierarchy.

## Skills

| Skill | What it does |
|-------|-------------|
| `instagram-pipeline` | Sync saved posts from Instagram API, download media, extract text (Whisper + OCR). Scripts bundled with skill. |
| `instagram-analysis` | Full analysis pipeline: raw posts → embeddings, topics, sentiment, networks, temporal patterns, psychological profile |
| `instagram-deep-dive` | Build narrative archives from a single collection: entities, events, narratives, claims, chronicles, profiles |
| `video-analysis` | Multi-model video extraction: frames + full-video → structured data with trust hierarchy |

## Templates

Generalized, runnable scripts the agent adapts to your collection. Not copy-paste — the agent reads these as reference implementations and customizes for your data.

```
templates/
├── pipeline/          # 8 analysis scripts (synthesis → psych profile)
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

## Examples

- [`sample_config.py`](examples/sample_config.py) — Fictional "Climate" collection config showing all fields

## How Templates Work

Templates use a shared `config.py` pattern. You copy it, fill in your collection details, and the agent runs templates in order:

```python
# config.py — your collection's identity
COLLECTION_NAME = "Climate"
COLLECTION_SLUG = "climate"
COLLECTION_PREFIX = "climate"  # Convex table prefix

# These start empty — populated as you run the pipeline
ALIAS_TABLE = {}           # Step 2: entity aliases
NARRATIVE_FRAMES = []      # Step 5: frames discovered from your data
CLAIM_CATEGORIES = []      # Step 6: claim types for your domain
```

The real customization is domain vocabulary (alias tables, frame taxonomies, claim categories), not paths or flags. That's why `config.py` beats argparse.

## Requirements

- Python 3.12+
- Claude Code with Max plan (subagents are free)
- Convex account (for web dashboard)
- ffmpeg (for video pipeline only)

## Architecture

Built from analyzing 11,323 Instagram saved posts across 5 collection deep dives (Gaza, Food, Counterculture, AI, Hundetrening). Every template has been battle-tested on real data.

**Design principles:**
- **Agentic-first:** Prefer LLM subagents over deterministic scripts. The quality ceiling is always higher.
- **Discovery over configuration:** Narrative frames, account types, and entity aliases emerge from your data — not copied from another collection.
- **Trust hierarchy:** For multi-model pipelines, establish ground truth (Opus) and additive-only enrichment (Gemini).
- **Editorial, not SaaS:** The frontend follows data journalism aesthetics (ProPublica, The Pudding), not dashboard conventions.

## Author

Simon Strumse
