---
name: instagram-analysis
description: >
  Analyze Instagram saved posts: synthesis, embeddings, UMAP, topics, sentiment,
  networks, temporal patterns, psychological profile, and dashboard.
---

# Instagram Saved Posts — Full Analysis Pipeline

> Skill for reproducing the complete analysis pipeline: from raw Instagram saved posts JSON to an interactive multi-page dashboard with semantic search, topic modeling, sentiment analysis, network graphs, psychological profiling, and local media serving.

## Prerequisites

- **Prior skill:** Run `instagram-pipeline` first to get `saved_posts.json` with captions, media, and extracted text
- **Media:** `data/media/instagram/{username}/{post_id}_{hash}.jpg|mp4` (downloaded by pipeline skill)
- **Python:** 3.12+ with venv
- **Hardware:** Apple Silicon recommended (MPS GPU for sentiment), works on any machine

### Required Post Schema

Each post must have at minimum:
```json
{
  "id": "string",
  "text": "caption text",
  "author": {"username": "string"},
  "collections": ["string"],
  "created_at": "ISO datetime",
  "vision_analysis": {
    "mood": "string", "tone": "string", "categories": ["string"],
    "tags": ["string"], "content_style": "string", "humor_type": "string|list",
    "sarcasm_level": "int|float|string", "language": "string"
  },
  "extracted_text": {"audio_transcripts": [], "ocr_texts": []},
  "final_explainer": "synthesized paragraph (100-400 words)"
}
```

**If `vision_analysis` is missing** (it will be after `instagram-pipeline`), run Phase 0a first.
**If `final_explainer` is missing**, run Phase 0b (synthesis) first.

---

## Phase 0a: Vision Analysis (if needed)

**When:** Posts lack `vision_analysis` field. This is the case when coming directly from `instagram-pipeline`.

Use a Claude subagent (free on Max plan) or Gemini 2.0 Flash to analyze each post's images/video frames and produce structured visual metadata: mood, tone, categories, tags, content_style, humor_type, sarcasm_level, language.

**Approach:** For each post with local media, send the first image (or a video frame) to a vision model with a prompt like:

```
Analyze this Instagram post image. Return JSON with:
- mood (one word), tone (one word)
- categories (list of 2-5 content categories)
- tags (list of 5-15 descriptive tags)
- content_style (e.g., "documentary", "meme", "infographic", "selfie")
- humor_type (e.g., "none", "satire", "absurdist", "observational")
- sarcasm_level (0-10 integer)
- language (ISO code, e.g., "en", "nb", "ar")
```

Save results as `vision_analysis` on each post in `saved_posts.json`. Process in batches, checkpoint frequently.

**Note:** This step can also run in parallel with Phase 0b since they write different fields.

---

## Phase 0b: Synthesis (if needed)

**When:** Posts lack `final_explainer` field.

**Template:** `templates/pipeline/synthesis_runner.py`

Synthesizes caption + OCR + audio + vision into one searchable paragraph per post.

**Two modes — ask the user which they prefer:**

| Mode | Cost | Speed | How it works |
|------|------|-------|-------------|
| `--mode subagent` (default) | **Free** on Max plan | Agent-driven loop | Generates prompt files → agent feeds to subagents |
| `--mode api` | **Paid** (Anthropic API key) | Automated batch | Direct API calls, fully scripted |

**Run (free, default):**
```bash
python3 synthesis_runner.py                # generates prompts in data/synthesis_prompts/
python3 synthesis_runner.py --stats        # check progress
```
Then feed each prompt file to a Claude Haiku subagent and merge results back.

**Run (paid, automated):**
```bash
ANTHROPIC_API_KEY=sk-... python3 synthesis_runner.py --mode api
```

**What it does:**
1. Finds posts without `final_explainer`
2. Builds compact input (caption + OCR + audio + vision metadata)
3. Batches of 15 posts → generates prompts or sends to API
4. Results merged into source JSON with atomic writes
5. Checkpoints every 20 posts (safe to interrupt and resume)

**Gotchas:**
- Posts with `extraction_status: "partial:no_audio"` are skipped (run audio extraction first)
- Uses atomic tmp→rename writes for safety
- Deduplication is handled by the prompt (OCR and vision text_in_image often overlap)

---

## Phase 1: Install Dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install sentence-transformers lancedb bertopic hdbscan umap-learn \
            streamlit plotly networkx python-louvain pandas numpy scipy \
            scikit-learn torch transformers pyvis
```

---

## Phase 2: Embedding

**Template:** `templates/pipeline/embed_posts.py`

**Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-dim, 118M params)

**Why this model:**
- Multilingual (Norwegian + English + Arabic + 50 more)
- Fast on CPU (~100 texts/sec) — completes N posts in minutes
- 384-dim output is compact but effective
- DO NOT use `nomic-ai/nomic-embed-text-v2-moe` — MoE architecture is 500x slower on Apple Silicon

**Run:**
```bash
python3 embed_posts.py          # embed all posts
python3 embed_posts.py --stats  # verify + test query
```

**Output:**
- `data/embeddings.npy` — raw float32 array (N x 384)
- `data/post_ids.json` — index-to-post-ID mapping
- `instagram_vectors/` — LanceDB database with full-text + vector search

**LanceDB storage pattern (use pandas DataFrame, NOT raw dicts):**
```python
import pandas as pd
records = []
for i, post in enumerate(posts):
    records.append({
        "id": post_id,
        "text": str(explainer)[:2000],
        "mood": str(mood),
        "vector": embeddings[i].tolist(),  # MUST be .tolist()
        # ... other fields with explicit str()/int() casting
    })
df = pd.DataFrame(records)
table = db.create_table("posts", df)
```

**Known issue:** LanceDB fails with pyarrow type errors if you pass raw dicts or mixed types. Always cast explicitly and use pandas.

---

## Phase 3: UMAP Projections

**Template:** `templates/pipeline/compute_umap.py`

```bash
python3 compute_umap.py
```

**Parameters:** `n_neighbors=15, min_dist=0.1, metric="cosine"`

**Output:** `data/umap_2d.npy`, `data/umap_3d.npy`

---

## Phase 4: Topic Modeling

**Template:** `templates/pipeline/topic_model.py`

Uses BERTopic with pre-computed embeddings (no re-embedding needed).

```bash
python3 topic_model.py
```

**HDBSCAN settings:** `min_cluster_size=15, min_samples=5`
**Vectorizer:** `stop_words="english", min_df=5, max_df=0.95, ngram_range=(1,2)`

**Output:** `data/topic_assignments.json`, `data/topics_summary.json`, `data/bertopic_model/`

**Expected:** 10-20 topics depending on dataset diversity. ~40% may be outliers (topic -1).

---

## Phase 5: Sentiment Analysis

**Template:** `templates/pipeline/sentiment_analysis.py`

**Models:**
- Sentiment: `nlptown/bert-base-multilingual-uncased-sentiment` (1-5 stars)
- Emotion: `j-hartmann/emotion-english-distilroberta-base` (7 classes)

```bash
python3 sentiment_analysis.py
```

**Device:** Uses MPS (Apple Silicon GPU) if available, falls back to CPU.

**Output:** `data/sentiment_scores.json` — per-post sentiment stars + normalized score + dominant emotion + emotion probabilities.

---

## Phase 6: Network Analysis

**Template:** `templates/pipeline/network_analysis.py`

```bash
python3 network_analysis.py
```

**Account network:**
1. Groups posts by username → computes centroid embedding per account
2. Cosine similarity between centroids → threshold at 0.6
3. Louvain community detection

**Tag co-occurrence:**
1. Co-occurrence matrix from vision_analysis.tags
2. Filter: min tag count 10, min edge weight 5
3. Community detection

**Output:** `data/account_network.json`, `data/tag_network.json`

---

## Phase 7: Temporal Analysis

**Template:** `templates/pipeline/temporal_analysis.py`

```bash
python3 temporal_analysis.py
```

Computes: daily volume, topic distribution per month, sentiment trajectory (rolling averages), interest drift (Jensen-Shannon divergence), burst detection (z-score), collection growth curves.

**Output:** `data/temporal_patterns.json`

---

## Phase 8: Psychological Profile

**Template:** `templates/pipeline/psychological_profile.py`

```bash
python3 psychological_profile.py
```

**Known issue:** `humor_type` field can be a list instead of string. The script handles this:
```python
humor = va.get("humor_type", "none") or "none"
if isinstance(humor, list):
    humor = humor[0] if humor else "none"
```

Same for `sarcasm_level` — can be string, int, or float. Always type-check.

**Output:** `data/psychological_profile.json`

---

## Phase 9: Analysis Report + Exports

**Templates:** `templates/pipeline/analyze_posts.py`, `templates/pipeline/export_data.py`

```bash
python3 analyze_posts.py   # comprehensive statistics → data/analysis_report.json
python3 export_data.py     # CSV + JSON exports → data/exports/
```

**Exports in `data/exports/`:**
- `posts_full.csv` — all posts with computed fields
- `posts_enriched.json` — full posts with topics + sentiment + UMAP merged
- `accounts.csv` — per-account stats
- `topics.csv` — topic summaries

---

## Phase 10: Dashboard (build in your project)

Build a Streamlit dashboard to explore results. This is **not** a bundled template — you build it in your project directory.

```bash
pip install streamlit plotly pyvis
streamlit run dashboard/app.py
```

### Recommended pages

1. **Overview** — total posts, collection counts, date range, top accounts
2. **Search** — semantic search via LanceDB + faceted filters (collection, mood, topic)
3. **Galaxy** — UMAP 2D scatter (Plotly), color by collection/mood/topic/sentiment
4. **Topics** — BERTopic explorer: topic list, representative posts, stream chart over time
5. **Sentiment** — star distribution, emotion pie chart, monthly sentiment timeline
6. **Network** — account constellation + tag co-occurrence (pyvis)
7. **Profile** — PANAS affect gauge, behavior patterns, info diet, humor analysis
8. **Browse** — collection browser with local media thumbnails + video playback

### Media serving

Serve local media from `data/media/instagram/{username}/{post_id}_*.jpg|mp4`. Use `st.image()` / `st.video()` with local paths. If media is not on disk, degrade gracefully to a placeholder.

---

## Execution Order (with parallelization)

```
Phase 1: pip install
Phase 2: embed_posts.py  ─────┬── Phase 3: compute_umap.py
         (PARALLEL ↓)         ├── Phase 4: topic_model.py
Phase 5: sentiment_analysis.py├── Phase 6: network_analysis.py
                               │
                               ├── Phase 7: temporal_analysis.py  (needs 4+5)
                               ├── Phase 8: psychological_profile.py (needs 5+7)
                               ├── Phase 9: analyze + export (needs 4+5)
                               └── Phase 10: dashboard (needs all)
```

**Phases 2 and 5 are independent** — run in parallel for ~2x speedup.
**Phases 3, 4, 6 depend on 2** (need embeddings).
**Phase 7 depends on 4+5** (needs topics + sentiment).
**Phase 8 depends on 5+7** (needs sentiment + temporal patterns).

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: einops` | nomic model dependency | `pip install einops` or switch to MiniLM |
| `ArrowTypeError: Expected bytes, got 'list'` | LanceDB raw dict approach | Use pandas DataFrame with `.tolist()` for vectors |
| `TypeError: unhashable type: 'list'` | humor_type is list not string | `if isinstance(humor, list): humor = humor[0]` |
| Embedding takes hours | nomic MoE model on Apple Silicon | Switch to `paraphrase-multilingual-MiniLM-L12-v2` |
| `use_container_width` warning | Streamlit API deprecation | Replace with `width='stretch'` (cosmetic only) |

---

## Database

**Local:** LanceDB (embedded, file-based, Rust, no server process)
- Location: `instagram_vectors/`
- Vector search: `table.search(vector).limit(n).to_pandas()`
- Cosine similarity, 384-dim

**Hosted alternative:** Convex (native vector search) or Neon Postgres + pgvector.

---

## Next Skill in Chain

After this skill completes, you have a fully analyzed dataset: embeddings, topics, sentiment, networks, temporal patterns, psychological profile, and a Streamlit dashboard.

**To build an editorial deep dive** on a specific collection (chronicle, person profiles, creator pages), use `instagram-deep-dive`.

**To extract structured data from videos** (recipes, tutorials, exercises), use `video-analysis`.

Both skills expect the analysis outputs from this skill to already exist.
