"""
Step 7: Timeline Assembly

Merges events, entities, claims, and narrative frames into a unified chronology.
Assigns events to chapters and computes per-chapter statistics.

CHAPTERS must be defined in config.py before running (manual + data-driven).

Output: {OUTPUT_DIR}/{slug}_timeline.json
"""

import json
import sys
from collections import Counter, defaultdict

from config import (
    COLLECTION_SLUG, COLLECTION_NAME, CHAPTERS,
    OUTPUT_DIR, OUTPUT_POSTS,
)


def load_json(path):
    if not path.exists():
        print(f"  [not found: {path}]")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if not CHAPTERS:
        print("ERROR: CHAPTERS is empty in config.py.")
        print("Define chapters after reviewing event detection output (Step 3).")
        print("Format: [{\"id\": \"ch_01\", \"title\": \"...\", \"start\": \"YYYY-MM-DD\", \"end\": \"YYYY-MM-DD\"}]")
        sys.exit(1)

    # Load all analysis outputs
    posts = load_json(OUTPUT_POSTS) or []
    events_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_events.json") or {}
    entities_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_entities.json") or []
    narratives_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_narratives.json") or {}
    claims_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_claims.json") or {}
    accounts_data = load_json(OUTPUT_DIR / f"{COLLECTION_SLUG}_accounts.json") or {}

    events = events_data.get("events", [])
    narrative_map = {}
    for cls in narratives_data.get("classifications", []):
        narrative_map[cls["post_id"]] = cls

    claims = claims_data.get("claims", [])

    print(f"Loaded: {len(posts)} posts, {len(events)} events, "
          f"{len(entities_data)} entities, {len(claims)} claims")

    # Build lookups
    post_lookup = {p["id"]: p for p in posts}
    posts_by_day = defaultdict(list)
    for p in posts:
        day = p.get("day", "")
        if day:
            posts_by_day[day].append(p)

    # Assign events to chapters
    for event in events:
        event_date = event.get("period", "")
        event["chapterId"] = None
        for ch in CHAPTERS:
            if ch["start"] <= event_date <= ch["end"]:
                event["chapterId"] = ch["id"]
                break

    # Build chapter statistics
    chapter_results = []
    for ch in CHAPTERS:
        ch_id = ch["id"]
        start, end = ch["start"], ch["end"]

        # Posts in chapter
        ch_posts = [p for p in posts if start <= p.get("day", "") <= end]
        ch_events = [e for e in events if e.get("chapterId") == ch_id]

        # Emotion signature
        emotions = defaultdict(float)
        for p in ch_posts:
            for emo, score in (p.get("emotions", {}) or {}).items():
                emotions[emo] += score
        n = len(ch_posts) or 1
        emotion_sig = {k: round(v / n, 4) for k, v in sorted(emotions.items(), key=lambda x: -x[1])}

        # Frame distribution
        frames = Counter()
        for p in ch_posts:
            cls = narrative_map.get(p["id"], {})
            frame = cls.get("frame", "unclassified")
            frames[frame] += 1

        # Top entities (entities active in this period)
        top_entities = []
        for entity in entities_data:
            monthly = entity.get("monthlyCounts", {})
            start_month = start[:7]
            end_month = end[:7]
            count = sum(v for m, v in monthly.items() if start_month <= m <= end_month)
            if count > 0:
                top_entities.append({"name": entity["name"], "type": entity.get("entityType", ""), "count": count})
        top_entities.sort(key=lambda x: -x["count"])

        # Claims in chapter
        ch_claims = [c for c in claims if start <= c.get("date", "") <= end]

        chapter_results.append({
            "chapterId": ch_id,
            "title": ch["title"],
            "subtitle": ch.get("subtitle", ""),
            "description": ch.get("description", ""),
            "startDate": start,
            "endDate": end,
            "postCount": len(ch_posts),
            "eventCount": len(ch_events),
            "claimCount": len(ch_claims),
            "emotionSignature": emotion_sig,
            "frameDistribution": dict(frames.most_common()),
            "topEntities": top_entities[:10],
            "sortOrder": CHAPTERS.index(ch),
        })

    # Print summary
    print(f"\n{'='*60}")
    print(f"  Timeline Assembly: {COLLECTION_NAME}")
    print(f"{'='*60}")
    for ch in chapter_results:
        print(f"\n  {ch['chapterId']}: {ch['title']}")
        print(f"    {ch['startDate']} → {ch['endDate']}")
        print(f"    {ch['postCount']} posts, {ch['eventCount']} events, {ch['claimCount']} claims")
        top_frame = max(ch["frameDistribution"], key=ch["frameDistribution"].get) if ch["frameDistribution"] else "?"
        print(f"    Dominant frame: {top_frame}")
    print(f"{'='*60}")

    # Build chronicle index (posts grouped by chapter → week)
    chronicle_chapters = []
    for ch in CHAPTERS:
        ch_posts_sorted = sorted(
            [p for p in posts if ch["start"] <= p.get("day", "") <= ch["end"]],
            key=lambda p: p.get("day", "")
        )
        weeks = defaultdict(list)
        for p in ch_posts_sorted:
            week = p.get("week", p.get("day", "")[:7])
            weeks[week].append(p["id"])

        chronicle_chapters.append({
            "chapterId": ch["id"],
            "weeks": [
                {"week": w, "postIds": ids}
                for w, ids in sorted(weeks.items())
            ],
        })

    # Save
    output = {
        "chapters": chapter_results,
        "events": events,
        "chronicle_index": chronicle_chapters,
        "stats": {
            "total_posts": len(posts),
            "total_events": len(events),
            "total_claims": len(claims),
            "total_entities": len(entities_data),
            "chapter_count": len(CHAPTERS),
        },
    }

    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_timeline.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    main()
