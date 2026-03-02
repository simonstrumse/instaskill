"""
Step 9b: Account Profiles

Builds creator profiles keyed by @username. Two tiers:
  - Full profiles (>=ACCOUNT_FULL_TIER posts): dedicated creator page
  - Chip profiles (>=ACCOUNT_CHIP_TIER posts): compact card

Output: {OUTPUT_DIR}/{slug}_account_profiles.json
Export: {CONVEX_EXPORT_DIR}/{prefix}AccountProfiles.jsonl

Usage:
  python account_profiles.py build    # Build profiles from collection data
  python account_profiles.py export   # Export to Convex JSONL
  python account_profiles.py stats    # Print statistics
"""

import json
import sys
from collections import Counter, defaultdict

from config import (
    COLLECTION_SLUG, COLLECTION_PREFIX,
    ACCOUNT_FULL_TIER, ACCOUNT_CHIP_TIER,
    OUTPUT_DIR, CONVEX_EXPORT_DIR, OUTPUT_POSTS,
)


def load_posts():
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        return json.load(f)


def load_accounts():
    """Load account classifications if available."""
    path = OUTPUT_DIR / f"{COLLECTION_SLUG}_accounts.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        accounts = data.get("accounts", data) if isinstance(data, dict) else data
        return {a["username"]: a for a in accounts}
    return {}


def build_profiles(posts, accounts_by_name):
    """Build account profiles from posts + account classifications."""
    posts_by_user = defaultdict(list)
    for post in posts:
        username = post.get("author", {}).get("username", "")
        if username:
            posts_by_user[username].append(post)

    profiles = []
    for username, user_posts in posts_by_user.items():
        count = len(user_posts)
        if count < ACCOUNT_CHIP_TIER:
            continue

        tier = "full" if count >= ACCOUNT_FULL_TIER else "chip"
        account = accounts_by_name.get(username, {})
        display_name = user_posts[0].get("author", {}).get("display_name", username)

        user_posts.sort(key=lambda p: p.get("created_at", ""))

        # Date range
        dates = [p.get("day", p.get("created_at", "")[:10]) for p in user_posts]
        dates = [d for d in dates if d]
        first_seen = min(dates) if dates else ""
        last_seen = max(dates) if dates else ""

        # Monthly counts
        monthly = Counter()
        for p in user_posts:
            month = p.get("month", "")
            if month:
                monthly[month] += 1
        peak_month = monthly.most_common(1)[0][0] if monthly else ""

        # Emotion profile
        emotions = defaultdict(float)
        for p in user_posts:
            for emo, score in (p.get("emotions", {}) or {}).items():
                emotions[emo] += score
        n = len(user_posts)
        emotion_profile = {
            k: round(v / n, 4)
            for k, v in sorted(emotions.items(), key=lambda x: -x[1])
        } if emotions else {}

        # Top topics from vision tags
        topic_counter = Counter()
        for p in user_posts:
            va = p.get("vision_analysis", {}) or {}
            for tag in (va.get("tags", []) or []):
                if isinstance(tag, str):
                    topic_counter[tag.lower()] += 1

        profile = {
            "slug": username,
            "username": username,
            "displayName": display_name,
            "accountType": account.get("accountType", account.get("type", "other")),
            "tier": tier,
            "postCount": count,
            "postIds": [p["id"] for p in user_posts],
            "firstSeen": first_seen,
            "lastSeen": last_seen,
            "peakMonth": peak_month,
            "topTopics": [t for t, _ in topic_counter.most_common(10)],
            "emotionProfile": emotion_profile,
            "monthlyCounts": dict(sorted(monthly.items())),
        }
        profiles.append(profile)

    profiles.sort(key=lambda p: -p["postCount"])
    return profiles


def export_jsonl(profiles):
    """Export to Convex JSONL."""
    CONVEX_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = CONVEX_EXPORT_DIR / f"{COLLECTION_PREFIX}AccountProfiles.jsonl"

    with open(output, "w", encoding="utf-8") as f:
        for p in profiles:
            row = {
                "slug": p["slug"],
                "username": p["username"],
                "displayName": p["displayName"],
                "accountType": p["accountType"],
                "tier": p["tier"],
                "postCount": p["postCount"],
                "firstSeen": p["firstSeen"],
                "lastSeen": p["lastSeen"],
                "topTopics": json.dumps(p.get("topTopics", []), ensure_ascii=False),
                "emotionProfile": json.dumps(p["emotionProfile"], ensure_ascii=False),
                "monthlyCounts": json.dumps(p["monthlyCounts"], ensure_ascii=False),
            }
            if p.get("bio"):
                row["bio"] = p["bio"]
            if p.get("photoUrl"):
                row["photoUrl"] = p["photoUrl"]
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Exported {len(profiles)} profiles → {output}")


def print_stats(profiles):
    """Print profile statistics."""
    full = [p for p in profiles if p["tier"] == "full"]
    chip = [p for p in profiles if p["tier"] == "chip"]
    type_counts = Counter(p["accountType"] for p in profiles)

    print(f"\n{'='*60}")
    print(f"  Account Profiles — {COLLECTION_SLUG}")
    print(f"{'='*60}")
    print(f"  Total:  {len(profiles)}")
    print(f"  Full:   {len(full)} (>={ACCOUNT_FULL_TIER} posts)")
    print(f"  Chip:   {len(chip)} (>={ACCOUNT_CHIP_TIER} posts)")
    print(f"\n  Account types:")
    for t, c in type_counts.most_common():
        print(f"    {t:30s}: {c}")
    print(f"\n  Top creators:")
    for p in profiles[:15]:
        print(f"    @{p['username']:30s}: {p['postCount']} posts [{p['tier']}]")
    print(f"{'='*60}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python account_profiles.py [build|export|stats]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "build":
        posts = load_posts()
        accounts = load_accounts()
        profiles = build_profiles(posts, accounts)

        output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_account_profiles.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(profiles)} profiles → {output_path}")
        print_stats(profiles)

    elif command == "export":
        path = OUTPUT_DIR / f"{COLLECTION_SLUG}_account_profiles.json"
        if not path.exists():
            print(f"No profiles found. Run 'build' first.")
            return
        with open(path) as f:
            profiles = json.load(f)
        export_jsonl(profiles)

    elif command == "stats":
        path = OUTPUT_DIR / f"{COLLECTION_SLUG}_account_profiles.json"
        if not path.exists():
            print(f"No profiles found. Run 'build' first.")
            return
        with open(path) as f:
            profiles = json.load(f)
        print_stats(profiles)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
