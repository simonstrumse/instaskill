---
name: instagram-analysis
description: >
  Running the full Instagram saved posts analysis pipeline: from raw saved_posts.json
  through synthesis, embeddings, UMAP, topic modeling, sentiment, network analysis,
  temporal patterns, psychological profiling, and Streamlit dashboard. Use when
  reproducing or extending the analysis pipeline, running individual phases, debugging
  pipeline errors, or setting up the pipeline in a new environment.

  Trigger when:
  - User asks to run or re-run the analysis pipeline
  - User asks about embedding, topic modeling, sentiment analysis, or similar scripts
  - User encounters LanceDB, BERTopic, UMAP, or sentence-transformers errors
  - User asks about the Streamlit dashboard or specific dashboard pages
  - User asks about synthesis (final_explainer field) or Claude Haiku API integration
---

# Instagram Saved Posts — Full Analysis Pipeline

> Skill for reproducing the complete analysis pipeline: from raw Instagram saved posts JSON to an interactive multi-page dashboard with semantic search, topic modeling, sentiment analysis, network graphs, psychological profiling, and local media serving.

## Prerequisites

- **Input:** Your `saved_posts.json` — Instagram saved posts with multi-modal fields
- **Media:** `data/media/instagram/{username}/{post_id}_{hash}.jpg|mp4` (optional, for local thumbnails)
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

If `final_explainer` is missing, run synthesis first (Phase 0).

---

## Phase 0: Synthesis (if needed)

**When:** Posts lack `final_explainer` field.

**Template:** `templates/pipeline/synthesis_runner.py`

Calls Claude Haiku API to synthesize caption + OCR + audio + vision into one searchable paragraph per post.

**Key settings:**
```python
MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 15        # posts per API call
SAVE_EVERY = 20        # save checkpoint frequency
RATE_LIMIT_DELAY = 1.0 # seconds between calls
```

**Run:**
```bash
ANTHROPIC_API_KEY=sk-... python3 synthesis_runner.py
python3 synthesis_runner.py --stats  # check progress
```

**What it does:**
1. Finds posts without `final_explainer`
2. Builds compact input (caption + OCR + audio + vision metadata)
3. Sends batches of 15 to Haiku with synthesis prompt
4. Merges results into source JSON with fcntl file locking
5. Saves every 20 posts (safe to interrupt and resume)

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

```bash
python3 analyze_posts.py   # comprehensive statistics
python3 export_data.py     # CSV + JSON exports
```

**Exports in `data/exports/`:**
- `posts_full.csv` — all posts with computed fields
- `posts_enriched.json` — full posts with topics + sentiment + UMAP merged
- `accounts.csv` — per-account stats
- `topics.csv` — topic summaries

---

## Phase 10: Dashboard

### Launch
```bash
streamlit run dashboard/app.py
```

### Pages
1. **Overview** (`app.py`) — metrics, charts
2. **Search** (`pages/1_search.py`) — semantic search via LanceDB + faceted filters
3. **Galaxy** (`pages/2_galaxy.py`) — UMAP 2D scatter (Plotly), color by collection/mood/topic/sentiment
4. **Topics** (`pages/3_topics.py`) — BERTopic explorer + stream chart
5. **Sentiment** (`pages/4_sentiment.py`) — star distribution, emotion pie, monthly timeline
6. **Network** (`pages/5_network.py`) — account constellation + tag co-occurrence
7. **Profile** (`pages/6_profile.py`) — PANAS affect gauge, behavior, info diet, humor
8. **Browse** (`pages/7_browse.py`) — collection browser with local media thumbnails + video

### Media Serving
The dashboard serves local media from `data/media/instagram/{username}/{post_id}_*.jpg|mp4` via `dashboard/media_helper.py`. If media is not on disk, it degrades gracefully to "No image."

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
**Phases 7, 8 depend on 4+5** (need topics + sentiment).

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
