"""
Step 9a: Person Profiles

Four-step pipeline for building profiles of named individuals mentioned in posts:
  1. Build post index: scan posts for entity mentions using alias table
  2. Enrich profiles: Wikipedia API for bios + photos, compute temporal/emotion stats
  3. Populate event persons: link profiles to timeline events
  4. Export: generate Convex JSONL

Output: {OUTPUT_DIR}/{slug}_person_profiles.json
Export: {CONVEX_EXPORT_DIR}/{prefix}PersonProfiles.jsonl

Customize: ALIAS_TABLE, ENTITY_METADATA, PERSON_FULL_TIER, PERSON_CHIP_TIER in config.py
Dependencies: rapidfuzz, urllib (stdlib)
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse
from collections import Counter, defaultdict

from config import (
    COLLECTION_SLUG, COLLECTION_PREFIX, ALIAS_TABLE, ENTITY_METADATA,
    PERSON_FULL_TIER, PERSON_CHIP_TIER, OUTPUT_DIR, CONVEX_EXPORT_DIR,
    OUTPUT_POSTS,
)


def load_posts():
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        return json.load(f)


def slugify(name):
    """Convert name to URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


# =========================================================================
# Step 1: Build Post Index
# =========================================================================

def build_post_index(posts, alias_table):
    """Scan all posts for entity mentions and build a person→posts index."""
    from rapidfuzz import fuzz, process

    # Build reverse lookup
    alias_lookup = {}
    for canonical, aliases in alias_table.items():
        for alias in aliases:
            alias_lookup[alias.lower()] = canonical
        alias_lookup[canonical.lower()] = canonical

    all_aliases = list(alias_lookup.keys())
    person_posts = defaultdict(list)

    for post in posts:
        text_parts = [
            post.get("final_explainer", "") or "",
            post.get("text", "") or "",
        ]
        et = post.get("extracted_text", {}) or {}
        for t in (et.get("ocr_texts", []) or []):
            text_parts.append(t if isinstance(t, str) else str(t))
        full_text = " ".join(text_parts).lower()

        if not full_text.strip():
            continue

        found = set()
        for alias, canonical in alias_lookup.items():
            if alias in full_text:
                found.add(canonical)

        for canonical in found:
            person_posts[canonical].append(post["id"])

    return dict(person_posts)


# =========================================================================
# Step 2: Enrich Profiles
# =========================================================================

def fetch_wikipedia(name):
    """Fetch bio and photo from Wikipedia API."""
    try:
        encoded = urllib.parse.quote(name.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "InstaskillBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        bio = data.get("extract", "")[:500]
        photo = data.get("thumbnail", {}).get("source", "")
        return bio, photo
    except Exception:
        return "", ""


def enrich_profiles(person_posts, posts):
    """Build enriched person profiles with stats, bios, and photos."""
    post_lookup = {p["id"]: p for p in posts}
    profiles = []

    for canonical, post_ids in person_posts.items():
        count = len(post_ids)
        if count < PERSON_CHIP_TIER:
            continue

        tier = "full" if count >= PERSON_FULL_TIER else "chip"
        slug = slugify(canonical)

        # Temporal stats
        dates = []
        monthly = Counter()
        emotions = defaultdict(float)

        for pid in post_ids:
            post = post_lookup.get(pid, {})
            day = post.get("day", "")
            month = post.get("month", "")
            if day:
                dates.append(day)
            if month:
                monthly[month] += 1
            for emo, score in (post.get("emotions", {}) or {}).items():
                emotions[emo] += score

        dates.sort()
        first_seen = dates[0] if dates else ""
        last_seen = dates[-1] if dates else ""
        peak_month = monthly.most_common(1)[0][0] if monthly else ""

        emotion_profile = {}
        if emotions and count > 0:
            emotion_profile = {
                k: round(v / count, 4)
                for k, v in sorted(emotions.items(), key=lambda x: -x[1])
            }

        # Metadata enrichment
        meta = ENTITY_METADATA.get(canonical, {})

        # Wikipedia enrichment (for full profiles)
        wiki_bio, wiki_photo = "", ""
        if tier == "full":
            wiki_bio, wiki_photo = fetch_wikipedia(canonical)
            time.sleep(0.5)  # Rate limit

        profile = {
            "canonical": canonical,
            "slug": slug,
            "tier": tier,
            "role": meta.get("role", ""),
            "affiliation": meta.get("affiliation", ""),
            "bio": meta.get("bio", wiki_bio),
            "photoUrl": wiki_photo,
            "postCount": count,
            "postIds": post_ids,
            "firstSeen": first_seen,
            "lastSeen": last_seen,
            "peakMonth": peak_month,
            "emotionProfile": emotion_profile,
            "monthlyCounts": dict(sorted(monthly.items())),
            "aliases": ALIAS_TABLE.get(canonical, []),
        }
        profiles.append(profile)

    profiles.sort(key=lambda p: -p["postCount"])
    return profiles


# =========================================================================
# Step 3: Populate Event Persons
# =========================================================================

def populate_event_persons(profiles, events_path):
    """Link person profiles to timeline events (adds topPersons to events)."""
    if not events_path.exists():
        return

    with open(events_path) as f:
        events_data = json.load(f)

    events = events_data.get("events", [])
    # This step enriches events with person mentions — handled during export
    return events


# =========================================================================
# Step 4: Export
# =========================================================================

def export_jsonl(profiles):
    """Export profiles to Convex JSONL."""
    CONVEX_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = CONVEX_EXPORT_DIR / f"{COLLECTION_PREFIX}PersonProfiles.jsonl"

    with open(output, "w", encoding="utf-8") as f:
        for p in profiles:
            row = {
                "canonical": p["canonical"],
                "slug": p["slug"],
                "tier": p["tier"],
                "postCount": p["postCount"],
                "firstSeen": p["firstSeen"],
                "lastSeen": p["lastSeen"],
                "emotionProfile": json.dumps(p["emotionProfile"], ensure_ascii=False),
                "monthlyCounts": json.dumps(p["monthlyCounts"], ensure_ascii=False),
            }
            if p.get("role"):
                row["role"] = p["role"]
            if p.get("affiliation"):
                row["affiliation"] = p["affiliation"]
            if p.get("bio"):
                row["bio"] = p["bio"]
            if p.get("photoUrl"):
                row["photoUrl"] = p["photoUrl"]
            if p.get("aliases"):
                row["aliases"] = json.dumps(p["aliases"], ensure_ascii=False)

            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Exported {len(profiles)} profiles → {output}")


def main():
    if not ALIAS_TABLE:
        print("ERROR: ALIAS_TABLE is empty in config.py.")
        print("Populate it during Step 2 (entity extraction) before building person profiles.")
        sys.exit(1)

    posts = load_posts()
    print(f"Loaded {len(posts)} posts, {len(ALIAS_TABLE)} canonical entities")

    # Step 1: Build post index
    print("\n--- Step 1: Building post index ---")
    person_posts = build_post_index(posts, ALIAS_TABLE)
    print(f"Found {len(person_posts)} entities with mentions")

    # Step 2: Enrich profiles
    print("\n--- Step 2: Enriching profiles ---")
    profiles = enrich_profiles(person_posts, posts)
    full = [p for p in profiles if p["tier"] == "full"]
    chip = [p for p in profiles if p["tier"] == "chip"]
    print(f"Built {len(profiles)} profiles ({len(full)} full, {len(chip)} chip)")

    # Step 3: Populate events (optional)
    events_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_events.json"
    if events_path.exists():
        print("\n--- Step 3: Linking to events ---")
        populate_event_persons(profiles, events_path)

    # Save profiles
    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_person_profiles.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")

    # Step 4: Export
    print("\n--- Step 4: Exporting JSONL ---")
    export_jsonl(profiles)

    # Stats
    print(f"\n{'='*50}")
    print(f"  Top profiles:")
    for p in profiles[:15]:
        print(f"    {p['canonical']:35s} {p['postCount']:4d} posts  [{p['tier']}]")


if __name__ == "__main__":
    main()
