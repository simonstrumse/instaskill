---
name: instagram-deep-dive
description: >
  Build editorial deep dives from Instagram collections: chronicles, person profiles,
  creator pages, entity extraction, event detection, and Convex-backed frontend.
---

# Instagram Deep Dive Skill

Build narrative deep dives from Instagram saved post collections — editorial data magazines with chronicles, person profiles, creator pages, and exploratory analysis. Each deep dive discovers the unique value of its collection and builds a custom interface to surface it.

## Trigger Keywords

- "deep dive", "build a deep dive", "new deep dive"
- "chronicle", "timeline", "narrative archive"
- "person profiles", "creator profiles", "account profiles"
- "build the [collection] section", "analyze this collection"
- "Convex schema", "import to Convex", "deep dive frontend"

## Prerequisites

- **Prior skills:** Run `instagram-pipeline` then `instagram-analysis` first
- Posts with `vision_analysis`, `extracted_text`, `final_explainer`, embeddings, topics, sentiment
- Python 3.12+ with venv — install deep-dive deps: `pip install -r templates/deep-dive/requirements.txt`
- Node.js 18+ (for Convex + Next.js frontend)
- The collection must have >200 posts and a coherent theme

## Philosophy

You are building an **editorial data magazine**, not a SaaS dashboard. Think ProPublica, The Pudding, Bloomberg Businessweek — narrative-driven, data-rich, designed to be read. Every deep dive should feel like opening a publication, not logging into an admin panel.

The pipeline is **half mechanical, half discovery**. Steps 1-3 and 8-10 are reproducible. Steps 4-7 are where you discover what makes THIS collection unique — and that discovery should drive the interface design.

---

## The 10-Step Pipeline

### Step 1: Extract (mechanical)

**Template:** `templates/deep-dive/extract.py` | **Config:** `templates/deep-dive/config.py`

Filter posts by collection, attach analysis data, compute cross-collection flags.

```python
# config.py
COLLECTION_FILTER_NAMES = ["YourCollection"]
```

Key questions to answer before proceeding:
- How many posts? (>200 is viable, >1000 is rich)
- Date range? (affects chapter granularity)
- How many unique accounts? (affects profile strategy)
- What other collections do these posts overlap with?

### Step 2: Entity Extraction (adaptive)

**Template:** `templates/deep-dive/entity_extraction.py`

**Choose your approach based on the collection type:**

| Collection type | Approach | Example |
|----------------|----------|---------|
| Political / figure-heavy | Alias-based NER with fuzzy matching | Collections about conflict, politics, media |
| Creator / account-heavy | Account-based profiles from post metadata | Collections about food, art, tutorials |
| Mixed | Both — accounts for creators, aliases for mentioned figures | Most collections |

For alias-based: Build a domain-specific alias table mapping name variants to canonical forms. Use `rapidfuzz` for fuzzy matching (no spaCy needed). Configure in `config.py`:

```python
ALIAS_TABLE = {
    "Canonical Name": ["alias1", "alias2", "shortened"],
}
```

For account-based: Group posts by `author.username`, compute per-account stats.

### Step 3: Event Detection (mechanical, adaptive threshold)

**Template:** `templates/deep-dive/event_detection.py`

Detect significant days/weeks using z-score burst detection. Configure thresholds in `config.py`:

```python
EVENT_AGGREGATION = "daily"   # "daily" for >500 posts, "weekly" for <300
EVENT_Z_THRESHOLD = 2.0       # 2.0 for large, 1.5 for small/noisy
EVENT_PELT_PENALTY = 10       # Higher = fewer changepoints
```

Uses three complementary methods:
1. **PELT changepoints** — structural breaks in the time series
2. **Z-score bursts** — anomaly detection for spike events
3. **Kleinberg** — hierarchical burst model for sustained activity

### Step 4: Account Classification (discovery)

**Template:** `templates/deep-dive/account_classification.py`

Classify Instagram accounts by type. **This is where you discover the ecosystem.**

Don't copy types from another deep dive. Look at what's actually in YOUR data:
- What kinds of accounts post here? (news orgs, activists, creators, satirists, translators?)
- Which accounts are bridges between collections?
- What does the centrality graph reveal about information flow?

Output: account types, community assignments, centrality scores.

### Step 5: Narrative Classification (discovery)

**Template:** `templates/deep-dive/narrative_classification.py`

Use Claude subagents to classify posts into domain-specific frames. **This is the most important discovery step.**

The frames should emerge from the data, not be imported. The template includes a **discovery mode** that samples 200 posts and identifies recurring frames before classification begins.

**Use Claude subagents (free on Max plan), not direct API calls.** Sonnet for complex synthesis, Haiku for classification.

### Step 6: Claim Extraction (mechanical)

**Template:** `templates/deep-dive/claim_extraction.py`

Extract factual claims from post explainers with check-worthiness scores. Use Haiku subagents. Configure categories in `config.py`:

```python
CLAIM_CATEGORIES = ["category1", "category2", ...]
```

### Step 7: Timeline Assembly (mechanical)

**Template:** `templates/deep-dive/timeline_assembly.py`

Combine events + entities + claims + frames into a chronology. Assign events to chapters.

**Chapter definition is manual + data-driven:**
- Look at the temporal clustering from Step 3
- Identify 4-6 natural breakpoints
- Name chapters based on what the data shows, not what you expect
- Configure in `config.py`:

```python
CHAPTERS = [
    {"id": "ch_01", "title": "...", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
]
```

### Step 8: Chronicle Generation (mechanical)

**Template:** `templates/deep-dive/chronicle_generation.py`

Use Claude subagents to write editorial prose for:
- Chronicle header (what is this archive?)
- Chapter introductions (what happened in this period?)
- Epilogue (what does this collection tell us?)

### Step 9: Profile Systems (mechanical, adaptive)

**Templates:** `templates/deep-dive/person_profiles.py`, `templates/deep-dive/account_profiles.py`

Build profiles for the people and accounts in this collection. Two systems:

#### Person Profiles (mentioned figures)
Pipeline: `build_post_index` → `enrich_profiles` → `populate_event_persons` → `export`

- Scan posts for entity mentions using alias table from Step 2
- Compute temporal stats (first/last seen, peak month, monthly counts)
- Compute emotional signature (average emotion distribution)
- Enrich with Wikipedia API (`/api/rest_v1/page/summary/{name}`) for bio + photo
- Two tiers configured in `config.py`:

```python
PERSON_FULL_TIER = 10   # ≥N posts → full profile page
PERSON_CHIP_TIER = 3    # N-M posts → chip profile
```

#### Account Profiles (Instagram creators)
- Group posts by `author.username`
- Compute emotion profiles, monthly counts, top topics from vision tags
- Two tiers configured in `config.py`:

```python
ACCOUNT_FULL_TIER = 5   # ≥N posts → full creator page
ACCOUNT_CHIP_TIER = 2   # N-M posts → card only
```

**Every deep dive should have at least one profile system. Most benefit from both.**

#### Photo Persistence (critical)

Instagram CDN URLs expire within hours. Never store them as permanent references.

**The pattern:**
1. During pipeline: download post thumbnails to permanent storage (Convex file storage, S3, or local disk)
2. Store a `photoStorageId` (or file path) on each profile — NOT the CDN URL
3. For profile photos: reuse an existing post thumbnail from that person/account
4. In queries: resolve the storage reference to a URL at read time

### Step 10: Export & Import (mechanical)

**Template:** `templates/deep-dive/convex_export.py`

Export everything to your database format (JSONL for Convex, SQL for Postgres, etc.).

---

## Database Layer

### Recommended: Convex

**Schema template:** `templates/convex/schema.ts`
**Query patterns:** `templates/convex/queries.ts`

Convex is the fastest path — `npx convex dev` just works, no Docker or database install. You get real-time reactivity, file storage for thumbnails, and vector search out of the box.

#### Data contract (what tables you need)

Every deep dive needs these tables (prefix with your collection name). See `reference/DATA_CONTRACT.md` for full field specs:

| Table | Purpose |
|-------|---------|
| `{prefix}Timeline` | Events with z-scores, emotion signatures, entity mentions |
| `{prefix}Chapters` | Narrative chapters with date ranges and descriptions |
| `{prefix}Accounts` | Account ecosystem (types, communities, centrality) |
| `{prefix}Entities` | Named entities (people, orgs, places) |
| `{prefix}Claims` | Factual claims with check-worthiness scores |
| `{prefix}PersonProfiles` | Mentioned figures (two-tier: full + chip) |
| `{prefix}AccountProfiles` | Creator profiles (two-tier: full + chip) |
| `{prefix}ChronicleContent` | Editorial prose (header, chapter intros, epilogue) |
| `{prefix}Analysis` | Pre-computed JSON blobs keyed by string |

Complex fields (arrays, nested objects) are stored as JSON strings and parsed in queries. This is a Convex pattern — other databases can use native JSON columns.

#### Convex-specific gotchas

- String queries are **case-sensitive** — `"Climate"` != `"climate"`. Always spot-check
- JSONL import **appends** by default — always use `--replace` flag
- Large JSON fields (>50KB) can truncate on import — use Node `ConvexHttpClient` mutation for oversized rows
- Non-interactive terminal: `CONVEX_DEPLOYMENT="dev:your-name" npx convex dev --once`
- File storage: upload thumbnails during pipeline, reference via `v.id("_storage")`

#### Import pattern
```bash
npx convex import --table {prefix}Timeline data/convex_export/{prefix}Timeline.jsonl --replace
```

### Alternative: Postgres

If you prefer Postgres, the data contract maps to standard tables. Use:
- `jsonb` columns for complex fields (emotionProfile, monthlyCounts)
- `pgvector` extension for embedding search
- A file server or S3 for thumbnail storage

---

## Frontend Patterns

**Templates:** `templates/frontend/layout.tsx`, `landing.tsx`, `chronicle.tsx`, `people.tsx`, `person-detail.tsx`

### Route structure

Each deep dive gets its own route group. For Next.js:
```
src/app/(your-collection)/
  your-collection/
    page.tsx          # Landing/overview
    chronicle/        # Scrollable timeline
    people/           # Profile cards (creators + mentioned figures)
    creator/[username]/ # Creator detail page
    person/[slug]/    # Person detail page
    timeline/         # Event explorer
    ...collection-specific pages
```

### Lazy loading for chronicles

Any chronicle with 50+ events needs lazy loading or it will crash the browser. Apply at three levels:
1. **Chapters:** First 1-2 eager, rest lazy (600px rootMargin)
2. **Weeks/events within chapters:** Each group lazy (400px rootMargin)
3. **Posts within events:** Native `loading="lazy"` on images, details on click

### People page pattern

Combine both profile systems on one page:
1. **Top section:** Creator cards with type filter pills, search, stats
2. **Section break**
3. **Bottom section:** Mentioned figures with role badges, search

---

## Adapting for a New Collection

The goal is to discover what makes each collection unique, then build an interface that surfaces that value. Don't copy another deep dive's structure — let the data tell you what pages to build.

### Discovery checklist

After running Steps 1-5, ask:
- What **account types** emerged? (This tells you the ecosystem)
- What **narrative frames** dominate? (This tells you the collection's voice)
- What **entities** appear most? (This tells you who/what the collection watches)
- What **emotional arc** does the timeline show? (This tells you the story)
- What makes this collection **different** from the others? (This is your hook)

### What a deep dive can look like (examples)

Each collection discovers its own unique angle. Here are examples of what different types of collections produced during development:

| Type | Size | Unique value | Custom interface |
|------|------|-------------|-----------------|
| News/conflict | ~7,000 | Chronological witness archive | Multi-page chronicle, accountability tracker, connection pages |
| Satirical/political | ~1,400 | Voice/subject analysis, satire detection | Power analysis, voices vs. subjects classification |
| Recipe/cooking | ~850 | Extractable recipes from video reels | Full cookbook with recipe detail pages, creator profiles |
| Tech/tools | ~200 | Fast-growing ecosystem tracking | Toolkit pages, trend detection, signal taxonomy |

### Minimum page quality checklist

Before shipping any deep dive page:
- [ ] Landing page loads in <2s with real data
- [ ] Chronicle lazy-loads (doesn't crash on 1000+ posts)
- [ ] Entity chips navigate to correct profile pages
- [ ] Profile photos persist (not CDN URLs)
- [ ] Search works across all entity types
- [ ] Mobile layout doesn't overflow
- [ ] Empty states handled (no blank pages for missing data)

---

## File Reference (templates)

| Template | Purpose |
|----------|---------|
| `templates/deep-dive/config.py` | Shared configuration for all scripts |
| `templates/deep-dive/extract.py` | Filter + attach analysis + cross-collection flags |
| `templates/deep-dive/entity_extraction.py` | Alias-based OR account-based entity extraction |
| `templates/deep-dive/event_detection.py` | Z-score + PELT + Kleinberg burst detection |
| `templates/deep-dive/account_classification.py` | LLM discovery of account types |
| `templates/deep-dive/narrative_classification.py` | Frame discovery + batch classification |
| `templates/deep-dive/claim_extraction.py` | Haiku claim extraction + check-worthiness |
| `templates/deep-dive/timeline_assembly.py` | Merge all analysis into chronology |
| `templates/deep-dive/chronicle_generation.py` | Editorial prose generation |
| `templates/deep-dive/person_profiles.py` | 4-step person profile pipeline |
| `templates/deep-dive/account_profiles.py` | Account-based creator profiles |
| `templates/deep-dive/convex_export.py` | Generic JSONL exporter |
| `templates/convex/schema.ts` | Database schema with {prefix} placeholders |
| `templates/convex/queries.ts` | Standard query patterns |
| `templates/frontend/*.tsx` | Annotated frontend page patterns |
