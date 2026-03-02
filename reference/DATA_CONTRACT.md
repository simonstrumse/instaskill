# Data Contract

Authoritative schema for all tables that templates produce. Every deep dive generates these 9 table types with a collection-specific prefix.

---

## Naming Convention

All tables use camelCase with the collection prefix:
- `{prefix}Timeline` — e.g., `climateTimeline`, `cookingTimeline`
- `{prefix}Chapters` — e.g., `climateChapters`
- etc.

The prefix is set in `config.py` as `COLLECTION_PREFIX`.

---

## Table Types

### 1. `{prefix}Timeline`

Events detected via burst analysis (z-score, PELT changepoints, Kleinberg).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `eventId` | `string` | yes | Unique identifier (e.g., `"evt_001"`) |
| `date` | `string` | yes | ISO date (`"2024-01-15"`) |
| `postCount` | `number` | yes | Posts in this event window |
| `zScore` | `number` | yes | Statistical significance |
| `burstType` | `string` | yes | `"point"`, `"sharp_spike"`, `"front_loaded"`, `"build_up"`, `"sustained"` |
| `chapterId` | `string` | yes | Parent chapter reference |
| `emotionSignature` | `string` | yes | JSON string: `{"anger": 0.3, "sadness": 0.5, ...}` |
| `frameDistribution` | `string` | yes | JSON string: `{"frame_name": count, ...}` |
| `topEntities` | `string` | yes | JSON string: `[{"name": "...", "type": "PERSON", "count": N}, ...]` |
| `topTopics` | `string` | no | JSON string: `[{"id": N, "label": "...", "count": N}, ...]` |
| `topAccounts` | `string` | no | JSON string: `["@username1", "@username2", ...]` |
| `description` | `string` | no | Human-readable event summary |

**Indexes:** `by_date` (date), `by_chapter` (chapterId)

---

### 2. `{prefix}Chapters`

Narrative sections grouping events into a chronological arc.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chapterId` | `string` | yes | Unique identifier (e.g., `"ch_01"`) |
| `title` | `string` | yes | Chapter heading |
| `subtitle` | `string` | no | Secondary heading |
| `description` | `string` | yes | 1-3 sentence summary |
| `startDate` | `string` | yes | ISO date |
| `endDate` | `string` | yes | ISO date |
| `postCount` | `number` | yes | Total posts in range |
| `eventCount` | `number` | yes | Events in this chapter |
| `emotionSignature` | `string` | yes | JSON string: aggregate emotions |
| `sortOrder` | `number` | yes | Display order (0-indexed) |

**Indexes:** `by_sortOrder` (sortOrder)

---

### 3. `{prefix}Accounts`

Instagram account ecosystem analysis.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | `string` | yes | Instagram @handle (without @) |
| `postCount` | `number` | yes | Posts from this account |
| `accountType` | `string` | yes | Collection-specific taxonomy (e.g., `"news_org"`, `"creator"`, `"activist"`) |
| `accountRole` | `string` | yes | `"original_source"` or `"amplifier"` |
| `community` | `string` | no | Louvain community label |
| `degreeCentrality` | `number` | no | Network centrality score |
| `betweennessCentrality` | `number` | no | Bridge score |
| `emotionProfile` | `string` | yes | JSON string: `{"anger": 0.2, ...}` |
| `activeMonths` | `string` | no | JSON string: `["2024-01", "2024-02", ...]` |
| `samplePostIds` | `string` | no | JSON string: `["post_id_1", ...]` |

**Indexes:** `by_username` (username), `by_type` (accountType)

---

### 4. `{prefix}Entities`

Named entities extracted via alias tables or NER.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | yes | Canonical entity name |
| `entityType` | `string` | yes | `"PERSON"`, `"ORG"`, `"GPE"`, `"LOC"`, `"EVENT"`, `"CONCEPT"` |
| `count` | `number` | yes | Total mentions |
| `firstSeen` | `string` | yes | ISO date of first mention |
| `lastSeen` | `string` | yes | ISO date of last mention |
| `monthlyCounts` | `string` | yes | JSON string: `{"2024-01": 5, "2024-02": 12, ...}` |
| `associatedEmotions` | `string` | yes | JSON string: dominant emotion per mention context |
| `coOccurrences` | `string` | no | JSON string: `[{"name": "...", "count": N}, ...]` |
| `lat` | `number` | no | Latitude (for GPE/LOC only) |
| `lon` | `number` | no | Longitude (for GPE/LOC only) |

**Indexes:** `by_name` (name), `by_type` (entityType), `by_count` (count)

---

### 5. `{prefix}Claims`

Extracted factual claims with check-worthiness scoring.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claimText` | `string` | yes | The claim as extracted |
| `category` | `string` | yes | Collection-specific (e.g., `"casualty"`, `"nutrition"`, `"capability"`) |
| `checkWorthiness` | `number` | yes | 1-5 scale |
| `postId` | `string` | yes | Source post reference |
| `date` | `string` | yes | ISO date |
| `source` | `string` | no | Attribution if identifiable |
| `confidence` | `number` | no | Extraction confidence 0-1 |

**Indexes:** `by_category` (category), `by_date` (date), `by_worthiness` (checkWorthiness)

---

### 6. `{prefix}Analysis`

Pre-computed aggregates stored as key-value JSON blobs.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | `string` | yes | Lookup key (e.g., `"daily_volume"`, `"hero_stats"`, `"emotion_arc"`) |
| `data` | `string` | yes | JSON string containing the full aggregate |

**Standard keys:**
- `daily_volume` — `{"2024-01-01": 5, ...}`
- `daily_emotions` — `{"2024-01-01": {"anger": 0.3, ...}, ...}`
- `daily_frames` — `{"2024-01-01": {"frame": count, ...}, ...}`
- `hero_stats` — `{"total_posts": N, "date_range": [...], "top_account": "...", ...}`
- `account_distribution` — `{"type": count, ...}`
- `entity_network` — `{"nodes": [...], "edges": [...]}`
- `emotion_arc` — monthly emotion aggregates

**Indexes:** `by_key` (key)

---

### 7. `{prefix}ChronicleContent`

Editorial prose generated by Claude subagents.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contentId` | `string` | yes | Unique identifier |
| `contentType` | `string` | yes | `"header"`, `"chapter_intro"`, `"epilogue"` |
| `chapterId` | `string` | no | For `chapter_intro` type |
| `title` | `string` | no | Section title |
| `body` | `string` | yes | Markdown prose |
| `sortOrder` | `number` | yes | Display order |

**Indexes:** `by_type` (contentType), `by_sortOrder` (sortOrder)

---

### 8. `{prefix}PersonProfiles`

Named individuals mentioned across posts (alias-based extraction).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `canonical` | `string` | yes | Canonical name |
| `slug` | `string` | yes | URL-safe slug |
| `tier` | `string` | yes | `"full"` or `"chip"` |
| `role` | `string` | no | `"journalist"`, `"politician"`, `"activist"`, etc. |
| `affiliation` | `string` | no | Organization or group |
| `bio` | `string` | no | 2-3 sentence biography |
| `photoUrl` | `string` | no | Wikipedia or stored photo URL |
| `postCount` | `number` | yes | Posts mentioning this person |
| `firstSeen` | `string` | yes | ISO date |
| `lastSeen` | `string` | yes | ISO date |
| `emotionProfile` | `string` | yes | JSON string: emotions in mention context |
| `monthlyCounts` | `string` | yes | JSON string: `{"2024-01": N, ...}` |
| `topCoOccurrences` | `string` | no | JSON string: frequently co-mentioned names |
| `aliases` | `string` | no | JSON string: `["alias1", "alias2", ...]` |

**Indexes:** `by_slug` (slug), `by_canonical` (canonical), `by_tier` (tier)

---

### 9. `{prefix}AccountProfiles`

Creator/account profiles grouped by @username.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | `string` | yes | Instagram @handle |
| `name` | `string` | no | Display name |
| `slug` | `string` | yes | URL-safe slug |
| `tier` | `string` | yes | `"full"` or `"chip"` |
| `accountType` | `string` | yes | Collection-specific taxonomy |
| `bio` | `string` | no | Generated biography |
| `photoUrl` | `string` | no | Profile photo URL |
| `postCount` | `number` | yes | Posts from this account |
| `firstSeen` | `string` | yes | ISO date |
| `lastSeen` | `string` | yes | ISO date |
| `emotionProfile` | `string` | yes | JSON string |
| `topTopics` | `string` | no | JSON string |
| `monthlyCounts` | `string` | no | JSON string |
| `crossCollectionFlags` | `string` | no | JSON string: `{"isGoldenContributor": true, ...}` |

**Indexes:** `by_username` (username), `by_slug` (slug), `by_tier` (tier), `by_type` (accountType)

---

## JSON Convention

All complex objects are stored as JSON **strings** in Convex, not native objects. This is because:
1. Convex doesn't support arbitrary nested objects in indexes
2. JSON strings can be of any size
3. Parsing on read is trivial and explicit

**Always parse on read:**
```typescript
const emotions = doc.emotionProfile ? JSON.parse(doc.emotionProfile) : {};
```

**Always stringify on write:**
```python
record["emotionProfile"] = json.dumps(emotion_dict, ensure_ascii=False)
```

## JSONL Export Format

All exports use newline-delimited JSON (JSONL). One record per line, no trailing comma, UTF-8:
```json
{"eventId":"evt_001","date":"2024-01-15","postCount":23,"zScore":3.45}
{"eventId":"evt_002","date":"2024-02-03","postCount":18,"zScore":2.87}
```

Strip `None`/`null` values before export — Convex handles missing fields better than explicit nulls.
