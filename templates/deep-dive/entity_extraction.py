"""
Step 2: Entity Extraction

Two approaches, selected via ENTITY_APPROACH in config.py:
  - "alias": Fuzzy-match against a hand-built alias table (for figure-heavy collections)
  - "account": Group by @username from post metadata (for creator-heavy collections)

Both produce a unified entity profile format with counts, temporal stats, and emotion signatures.

Output: {OUTPUT_DIR}/{slug}_entities.json
Dependencies: rapidfuzz (for alias mode)

Customize: Populate ALIAS_TABLE and ENTITY_METADATA in config.py before running alias mode.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from config import (
    COLLECTION_SLUG, ENTITY_APPROACH, ALIAS_TABLE, ENTITY_METADATA,
    FUZZY_MATCH_THRESHOLD, OUTPUT_DIR, OUTPUT_POSTS,
)


def load_posts():
    """Load extracted collection posts."""
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# ALIAS-BASED EXTRACTION
# =============================================================================

def build_alias_lookup(alias_table):
    """Build reverse lookup: lowercase alias → canonical name."""
    lookup = {}
    for canonical, aliases in alias_table.items():
        for alias in aliases:
            lookup[alias.lower()] = canonical
        lookup[canonical.lower()] = canonical
    return lookup


def extract_entities_alias(posts, alias_table):
    """Scan post text for alias matches using exact + fuzzy matching."""
    from rapidfuzz import fuzz, process

    alias_lookup = build_alias_lookup(alias_table)
    all_aliases = list(alias_lookup.keys())

    # Per-entity tracking
    entity_posts = defaultdict(list)       # canonical → [post dicts]
    entity_months = defaultdict(Counter)   # canonical → {month: count}
    entity_emotions = defaultdict(lambda: defaultdict(float))

    for post in posts:
        # Combine all text sources
        text_parts = []
        text_parts.append(post.get("final_explainer", "") or "")
        text_parts.append(post.get("text", "") or "")
        et = post.get("extracted_text", {}) or {}
        for t in (et.get("ocr_texts", []) or []):
            text_parts.append(t if isinstance(t, str) else str(t))
        full_text = " ".join(text_parts).lower()

        if not full_text.strip():
            continue

        # Track which entities we find in this post (deduplicate per post)
        found_in_post = set()

        # Exact match first
        for alias, canonical in alias_lookup.items():
            if alias in full_text and canonical not in found_in_post:
                found_in_post.add(canonical)

        # Fuzzy match on remaining text segments (words and bigrams)
        words = re.findall(r'\b\w+(?:\s+\w+)?\b', full_text)
        for word in words:
            if len(word) < 3:
                continue
            match = process.extractOne(
                word, all_aliases,
                scorer=fuzz.ratio,
                score_cutoff=FUZZY_MATCH_THRESHOLD,
            )
            if match:
                canonical = alias_lookup[match[0]]
                found_in_post.add(canonical)

        # Record findings
        month = post.get("month", "")
        emotions = post.get("emotions", {}) or {}

        for canonical in found_in_post:
            entity_posts[canonical].append(post)
            if month:
                entity_months[canonical][month] += 1
            for emo, score in emotions.items():
                entity_emotions[canonical][emo] += score

    return entity_posts, entity_months, entity_emotions


# =============================================================================
# ACCOUNT-BASED EXTRACTION
# =============================================================================

def extract_entities_account(posts):
    """Group posts by author username as entities."""
    entity_posts = defaultdict(list)
    entity_months = defaultdict(Counter)
    entity_emotions = defaultdict(lambda: defaultdict(float))

    for post in posts:
        username = post.get("author", {}).get("username", "")
        if not username:
            continue

        canonical = f"@{username}"
        entity_posts[canonical].append(post)

        month = post.get("month", "")
        emotions = post.get("emotions", {}) or {}

        if month:
            entity_months[canonical][month] += 1
        for emo, score in emotions.items():
            entity_emotions[canonical][emo] += score

    return entity_posts, entity_months, entity_emotions


# =============================================================================
# PROFILE BUILDING (shared)
# =============================================================================

def build_profiles(entity_posts, entity_months, entity_emotions):
    """Build unified entity profiles from extraction results."""
    profiles = []

    for canonical, posts in entity_posts.items():
        count = len(posts)
        if count < 2:  # Filter singletons
            continue

        dates = sorted(p.get("day", "") for p in posts if p.get("day"))
        first_seen = dates[0] if dates else ""
        last_seen = dates[-1] if dates else ""

        monthly = dict(sorted(entity_months[canonical].items()))
        peak_month = max(monthly, key=monthly.get) if monthly else ""

        # Normalize emotion profile
        emotions_raw = dict(entity_emotions[canonical])
        emotion_profile = {}
        if emotions_raw and count > 0:
            emotion_profile = {
                k: round(v / count, 4)
                for k, v in sorted(emotions_raw.items(), key=lambda x: -x[1])
            }

        # Entity type inference
        entity_type = "PERSON"
        if canonical.startswith("@"):
            entity_type = "ACCOUNT"

        # Check for metadata enrichment
        meta = ENTITY_METADATA.get(canonical, {})

        profile = {
            "name": canonical,
            "entityType": meta.get("type", entity_type),
            "count": count,
            "firstSeen": first_seen,
            "lastSeen": last_seen,
            "peakMonth": peak_month,
            "monthlyCounts": monthly,
            "emotionProfile": emotion_profile,
            "role": meta.get("role", ""),
            "affiliation": meta.get("affiliation", ""),
            "postIds": [p["id"] for p in posts],
        }
        profiles.append(profile)

    profiles.sort(key=lambda p: -p["count"])
    return profiles


def main():
    posts = load_posts()
    print(f"Loaded {len(posts)} posts")

    if ENTITY_APPROACH == "alias":
        if not ALIAS_TABLE:
            print("WARNING: ALIAS_TABLE is empty in config.py.")
            print("Run in discovery mode: scan 200 posts to identify key entities first.")
            print("Then populate ALIAS_TABLE and re-run.")
            sys.exit(1)
        print(f"Using alias-based extraction ({len(ALIAS_TABLE)} canonical entries)")
        entity_posts, entity_months, entity_emotions = extract_entities_alias(posts, ALIAS_TABLE)

    elif ENTITY_APPROACH == "account":
        print("Using account-based extraction")
        entity_posts, entity_months, entity_emotions = extract_entities_account(posts)

    else:
        print(f"Unknown ENTITY_APPROACH: {ENTITY_APPROACH}")
        sys.exit(1)

    profiles = build_profiles(entity_posts, entity_months, entity_emotions)
    print(f"\nBuilt {len(profiles)} entity profiles (min 2 mentions)")

    # Stats
    top_10 = profiles[:10]
    print(f"\nTop 10 entities:")
    for p in top_10:
        print(f"  {p['name']:40s} {p['count']:4d} mentions  ({p['firstSeen']} → {p['lastSeen']})")

    # Save
    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_entities.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    main()
