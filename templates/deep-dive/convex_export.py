"""
Step 10: Convex Export

Generic JSONL exporter for all deep dive tables. Reads analysis outputs and
produces JSONL files ready for `npx convex import --table {name} file.jsonl --replace`.

Exports 9 table types with the collection prefix from config.py.
Complex objects are serialized as JSON strings (Convex convention).

Output: {CONVEX_EXPORT_DIR}/*.jsonl
"""

import json
from collections import Counter

from config import (
    COLLECTION_SLUG, COLLECTION_PREFIX,
    OUTPUT_DIR, CONVEX_EXPORT_DIR, OUTPUT_POSTS,
)


def load_json(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_jsonl(table_name, records, export_dir):
    """Write records to JSONL, stripping None values."""
    path = export_dir / f"{table_name}.jsonl"
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            clean = {k: v for k, v in record.items() if v is not None}
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")
            count += 1
    size_kb = path.stat().st_size / 1024
    print(f"  {table_name}: {count} records ({size_kb:.0f} KB)")
    return count


def json_str(obj):
    """Serialize object to JSON string for Convex storage."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj  # Already a string
    return json.dumps(obj, ensure_ascii=False)


def export_timeline(events, prefix, export_dir):
    """Export timeline events."""
    records = []
    for e in events:
        records.append({
            "eventId": e.get("eventId", ""),
            "date": e.get("period", ""),
            "postCount": e.get("postCount", 0),
            "zScore": e.get("zScore", 0),
            "burstType": e.get("burstType", "point"),
            "chapterId": e.get("chapterId"),
            "emotionSignature": json_str(e.get("emotionSignature")),
            "topEntities": json_str(e.get("topEntities")),
            "topTopics": json_str(e.get("topTopics")),
            "topAccounts": json_str(e.get("topAccounts")),
            "dominantEmotion": e.get("dominantEmotion"),
            "isChangepoint": e.get("isChangepoint", False),
        })
    return write_jsonl(f"{prefix}Timeline", records, export_dir)


def export_chapters(chapters, prefix, export_dir):
    """Export narrative chapters."""
    records = []
    for ch in chapters:
        records.append({
            "chapterId": ch.get("chapterId", ""),
            "title": ch.get("title", ""),
            "subtitle": ch.get("subtitle"),
            "description": ch.get("description"),
            "startDate": ch.get("startDate", ""),
            "endDate": ch.get("endDate", ""),
            "postCount": ch.get("postCount", 0),
            "eventCount": ch.get("eventCount", 0),
            "emotionSignature": json_str(ch.get("emotionSignature")),
            "frameDistribution": json_str(ch.get("frameDistribution")),
            "topEntities": json_str(ch.get("topEntities")),
            "sortOrder": ch.get("sortOrder", 0),
        })
    return write_jsonl(f"{prefix}Chapters", records, export_dir)


def export_accounts(accounts, prefix, export_dir):
    """Export account ecosystem."""
    records = []
    for a in accounts:
        records.append({
            "username": a.get("username", ""),
            "postCount": a.get("postCount", 0),
            "accountType": a.get("accountType", "other"),
            "accountRole": a.get("accountRole", "amplifier"),
            "community": a.get("community"),
            "emotionProfile": json_str(a.get("emotionProfile")),
            "activeMonths": json_str(a.get("activeMonths")),
            "topTopics": json_str(a.get("topTopics")),
        })
    return write_jsonl(f"{prefix}Accounts", records, export_dir)


def export_entities(entities, prefix, export_dir, min_count=2):
    """Export named entities."""
    records = []
    for e in entities:
        if e.get("count", 0) < min_count:
            continue
        records.append({
            "name": e.get("name", ""),
            "entityType": e.get("entityType", "PERSON"),
            "count": e.get("count", 0),
            "firstSeen": e.get("firstSeen", ""),
            "lastSeen": e.get("lastSeen", ""),
            "monthlyCounts": json_str(e.get("monthlyCounts")),
            "associatedEmotions": json_str(e.get("emotionProfile")),
        })
    return write_jsonl(f"{prefix}Entities", records, export_dir)


def export_claims(claims, prefix, export_dir):
    """Export factual claims."""
    records = []
    for c in claims:
        records.append({
            "claimText": c.get("claimText", ""),
            "category": c.get("category", "general"),
            "checkWorthiness": c.get("checkWorthiness", 1),
            "postId": c.get("postId", ""),
            "date": c.get("date", ""),
            "source": c.get("source"),
        })
    return write_jsonl(f"{prefix}Claims", records, export_dir)


def export_analysis(posts, timeline_data, narratives_data, prefix, export_dir):
    """Export pre-computed analysis JSON blobs."""
    from collections import defaultdict

    records = []

    # Daily volume
    daily = Counter()
    daily_emotions = defaultdict(lambda: defaultdict(float))
    for p in posts:
        day = p.get("day", "")
        if day:
            daily[day] += 1
            for emo, score in (p.get("emotions", {}) or {}).items():
                daily_emotions[day][emo] += score

    records.append({
        "key": "daily_volume",
        "data": json_str(dict(sorted(daily.items()))),
    })

    # Daily emotions (normalized)
    daily_emo_norm = {}
    for day, emos in sorted(daily_emotions.items()):
        n = daily.get(day, 1)
        daily_emo_norm[day] = {k: round(v / n, 4) for k, v in emos.items()}
    records.append({
        "key": "daily_emotions",
        "data": json_str(daily_emo_norm),
    })

    # Hero stats
    accounts = set(p.get("author", {}).get("username", "") for p in posts)
    dates = sorted(p.get("day", "") for p in posts if p.get("day"))
    hero = {
        "total_posts": len(posts),
        "total_accounts": len(accounts),
        "date_range": [dates[0], dates[-1]] if dates else [],
        "total_events": timeline_data.get("stats", {}).get("total_events", 0) if timeline_data else 0,
    }
    records.append({"key": "hero_stats", "data": json_str(hero)})

    # Frame distribution (narrative)
    if narratives_data:
        records.append({
            "key": "frame_distribution",
            "data": json_str(narratives_data.get("distribution", {})),
        })

    return write_jsonl(f"{prefix}Analysis", records, export_dir)


def main():
    CONVEX_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = COLLECTION_PREFIX

    print(f"Exporting {COLLECTION_SLUG} → {CONVEX_EXPORT_DIR}/")
    print(f"Table prefix: {prefix}")
    print()

    # Load all data
    posts = load_json(OUTPUT_POSTS) or []
    timeline_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_timeline.json")
    entities = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_entities.json") or []
    narratives = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_narratives.json")
    claims_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_claims.json")
    accounts_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_accounts.json")

    total = 0

    # Timeline + Chapters
    if timeline_data:
        total += export_timeline(timeline_data.get("events", []), prefix, CONVEX_EXPORT_DIR)
        total += export_chapters(timeline_data.get("chapters", []), prefix, CONVEX_EXPORT_DIR)

    # Accounts
    if accounts_data:
        accts = accounts_data.get("accounts", accounts_data) if isinstance(accounts_data, dict) else accounts_data
        total += export_accounts(accts, prefix, CONVEX_EXPORT_DIR)

    # Entities
    if entities:
        total += export_entities(entities, prefix, CONVEX_EXPORT_DIR)

    # Claims
    if claims_data:
        total += export_claims(claims_data.get("claims", []), prefix, CONVEX_EXPORT_DIR)

    # Analysis blobs
    if posts:
        total += export_analysis(posts, timeline_data, narratives, prefix, CONVEX_EXPORT_DIR)

    # Person profiles and account profiles are exported by their own scripts
    print(f"\nTotal records exported: {total}")
    print(f"\nImport with:")
    for f in sorted(CONVEX_EXPORT_DIR.glob("*.jsonl")):
        table = f.stem
        print(f"  npx convex import --table {table} {f} --replace")


if __name__ == "__main__":
    main()
