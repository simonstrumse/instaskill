# Gotchas

Hard-won lessons from 5 collection deep dives (11,323 posts). Every item here caused at least one debugging session.

---

## Python / Data

### Vision analysis fields have inconsistent types
`vision_analysis.humor_type` can be a string (`"irony"`) or a list (`["irony", "absurdist"]`). Always type-check before processing:
```python
humor = post.get("vision_analysis", {}).get("humor_type", "none")
if isinstance(humor, list):
    humor = ", ".join(humor)
```

### Sarcasm level is never the type you expect
`vision_analysis.sarcasm_level` can be int (`3`), float (`3.0`), or string (`"3"`). Always cast:
```python
sarcasm = float(post.get("vision_analysis", {}).get("sarcasm_level", 0))
```

### LanceDB requires pandas DataFrames, not dicts
LanceDB will silently fail or produce garbage if you pass raw dicts. Always use explicit type casting:
```python
import pandas as pd
df = pd.DataFrame(records)
df["vector"] = df["vector"].apply(lambda x: x.tolist() if hasattr(x, "tolist") else x)
table = db.create_table("posts", df)
```

### Sentence-transformers MoE model loading
The `paraphrase-multilingual-MiniLM-L12-v2` model sometimes fails to load on first run due to cached config mismatches. Fix: delete `~/.cache/huggingface/` and re-download.

### BERTopic nr_topics="auto" can produce 1 topic
On small collections (<300 posts), HDBSCAN may cluster everything together. Lower `min_cluster_size` (try 10 or 8) or set a fixed `nr_topics`.

### NumPy embedding shape mismatches
When filtering a subset of posts, the embedding indices must be mapped 1:1. Build an explicit `post_id → embedding_idx` lookup before filtering:
```python
post_id_to_idx = {post["id"]: i for i, post in enumerate(all_posts)}
subset_indices = [post_id_to_idx[p["id"]] for p in subset_posts if p["id"] in post_id_to_idx]
subset_embeddings = all_embeddings[subset_indices]
```

### Date parsing across collections
Instagram dates come as ISO strings but some have timezone info, some don't. Always normalize:
```python
from datetime import datetime
date_str = post.get("saved_on") or post.get("created_at", "")
dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
```

---

## Convex

### Case-sensitive string queries
Convex string equality is case-sensitive. `"Climate"` ≠ `"climate"`. When filtering by collection name, match the exact casing in your data:
```typescript
// WRONG: ctx.db.query("posts").filter(q => q.eq(q.field("collection"), "climate"))
// RIGHT: use the exact string from saved_posts.json
ctx.db.query("posts").filter(q => q.eq(q.field("collection"), "Climate"))
```

### JSONL import needs --replace for updates
When re-importing data after pipeline changes, use `--replace` or you get duplicates:
```bash
npx convex import --table myTable data.jsonl --replace
```

### Large JSON fields truncate on import
Convex has field size limits. If your `analysis` JSON blob is very large, verify after import:
```javascript
// Verify: compare character count before/after
const doc = await ctx.db.query("analysis").first();
console.log(JSON.stringify(doc.data).length); // Should match source
```

### CDN URLs expire
Instagram media CDN URLs (`scontent-*.cdninstagram.com`) expire after hours/days. Never store them as permanent URLs. Either:
1. Download media locally during extraction
2. Use Convex file storage for permanent hosting
3. Accept broken images and re-scrape periodically

### Non-interactive Convex deployment
For CI/scripting, use the explicit deployment flag:
```bash
CONVEX_DEPLOYMENT=dev:your-deployment npx convex dev --once
```

### Large mutation arguments
Convex has argument size limits for mutations. For bulk imports, use the Node.js `ConvexHttpClient` instead of CLI:
```javascript
import { ConvexHttpClient } from "convex/browser";
const client = new ConvexHttpClient(process.env.CONVEX_URL);
// Batch in chunks of 100
```

### JSON stored as strings
Complex objects (emotionProfile, frameDistribution, topEntities, monthlyCounts) are stored as JSON *strings* in Convex, not native objects. Always parse on read:
```typescript
const parsed = doc.emotionProfile ? JSON.parse(doc.emotionProfile) : {};
```

---

## Frontend

### position: fixed is viewport-relative
Never add `window.scrollY` to fixed-position elements. Fixed positioning is already relative to the viewport:
```css
/* WRONG: top: ${scrollY + 100}px — jumps around */
/* RIGHT: top: 100px — stays put */
position: fixed;
top: 100px;
```

### Data caps must be at component level
When limiting displayed items (e.g., "top 10 entities"), filter in the component that renders them, not in the aggregation query. Otherwise, sorting/filtering in the UI operates on truncated data.

### Lazy loading thresholds
For chronicle pages with 1000+ posts, use three-level lazy loading:
1. **Page level:** Load chapters on scroll (IntersectionObserver)
2. **Chapter level:** Load weeks within visible chapter
3. **Post level:** Load post cards within visible week

### Streamlit use_container_width deprecated
Use `width='stretch'` instead of `use_container_width=True` for new Streamlit code.

### Entity chips must navigate consistently
If both `EntityChip` and `AccountChip` components link to profile pages, they must use the same navigation pattern. Inconsistent linking (one uses router, other uses query params) confuses users.

### Filter topEntities to correct type
When showing "Dominant voices" or "Key figures," filter entities to `PERSON` type only. Raw `topEntities` includes organizations, places, and events.

---

## LLM / Subagents

### Type variance in LLM outputs
Even with structured output prompts, LLMs return inconsistent types across batches. Always normalize:
```python
# Confidence might be "high", 0.9, or 90
def normalize_confidence(val):
    if isinstance(val, str):
        return {"high": 0.9, "medium": 0.6, "low": 0.3}.get(val.lower(), 0.5)
    if isinstance(val, (int, float)):
        return val / 100 if val > 1 else val
    return 0.5
```

### Trust hierarchy for multi-model pipelines
When using multiple models (e.g., Opus + Gemini), establish clear rules:
- **Ground truth model** (Opus): Never overridden by other models
- **Enrichment model** (Gemini): Only adds new fields, never replaces existing
- **Merge is deterministic:** Script, not LLM. No interpretation, just rules.

### Batch size affects quality
Larger batches (100+ posts) in a single LLM call degrade classification quality. Keep batches at 50-100 posts with clear examples in each prompt.

### Resume support is essential
Any batch LLM pipeline MUST support resume (checkpoint files). API calls fail, rate limits hit, connections drop. Write results after each batch:
```python
for i in range(0, len(posts), BATCH_SIZE):
    batch = posts[i:i+BATCH_SIZE]
    results = process_batch(batch)
    save_checkpoint(results, checkpoint_file)  # After EVERY batch
```

### Subagents vs direct API calls
On Claude Max plan, subagents (spawned via Claude Code) are free. Direct `anthropic` SDK API calls cost money. Always prefer subagents for data processing.
