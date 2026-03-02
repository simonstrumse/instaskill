"""
Phase 8: Psychological Profile

Builds a psychological profile from saving behavior:
  - PANAS affect mapping (positive/negative affect schedule)
  - Session clustering (30-min gap = new session)
  - Information diet analysis (topic diversity, entropy)
  - Humor/sarcasm profile
  - Behavior patterns (time-of-day, day-of-week)

Input: saved_posts.json, sentiment_scores.json, temporal_patterns.json
Output: data/psychological_profile.json

Known gotcha: humor_type can be list or string, sarcasm_level can be int/float/string.
"""

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
SENTIMENT_PATH = Path("data/sentiment_scores.json")
OUTPUT_PATH = Path("data/psychological_profile.json")
SESSION_GAP_MINUTES = 30  # Gap between sessions
# =======================================


def safe_humor(va):
    """Extract humor_type safely — can be string or list."""
    humor = va.get("humor_type", "none") or "none"
    if isinstance(humor, list):
        humor = humor[0] if humor else "none"
    return str(humor).lower()


def safe_sarcasm(va):
    """Extract sarcasm_level safely — can be int, float, or string."""
    val = va.get("sarcasm_level", 0)
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def entropy(counts):
    """Shannon entropy of a distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0
    probs = [c / total for c in counts.values() if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def main():
    with open(POSTS_PATH) as f:
        posts = json.load(f)
    with open(SENTIMENT_PATH) as f:
        sentiment = json.load(f)

    sent_map = {s["post_id"]: s for s in sentiment} if isinstance(sentiment, list) else sentiment
    print(f"Posts: {len(posts)}")

    # ========== PANAS Affect ==========
    positive_emotions = {"joy", "surprise"}
    negative_emotions = {"anger", "disgust", "fear", "sadness"}

    positive_total = 0
    negative_total = 0
    for p in posts:
        sent = sent_map.get(p["id"], {})
        emotions = sent.get("emotions", {})
        for emo, score in emotions.items():
            if emo in positive_emotions:
                positive_total += score
            elif emo in negative_emotions:
                negative_total += score

    n = len(posts) or 1
    panas = {
        "positive_affect": round(positive_total / n, 4),
        "negative_affect": round(negative_total / n, 4),
        "ratio": round(positive_total / (negative_total + 0.001), 2),
    }

    # ========== Session Clustering ==========
    timestamps = []
    for p in posts:
        ts = p.get("saved_on") or p.get("created_at", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                timestamps.append(dt)
            except (ValueError, TypeError):
                pass

    timestamps.sort()
    sessions = []
    if timestamps:
        session_start = timestamps[0]
        session_posts = 1
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
            if gap > SESSION_GAP_MINUTES:
                sessions.append({
                    "start": session_start.isoformat(),
                    "posts": session_posts,
                    "duration_min": round((timestamps[i-1] - session_start).total_seconds() / 60),
                })
                session_start = timestamps[i]
                session_posts = 1
            else:
                session_posts += 1
        sessions.append({
            "start": session_start.isoformat(),
            "posts": session_posts,
        })

    session_lengths = [s["posts"] for s in sessions]

    # ========== Behavior Patterns ==========
    hour_counts = Counter()
    day_counts = Counter()
    for dt in timestamps:
        hour_counts[dt.hour] += 1
        day_counts[dt.strftime("%A")] += 1

    # ========== Information Diet ==========
    topic_counts = Counter()
    collection_counts = Counter()
    mood_counts = Counter()
    for p in posts:
        va = p.get("vision_analysis", {}) or {}
        mood = va.get("mood", "unknown")
        mood_counts[mood] += 1
        for col in (p.get("collections") or []):
            collection_counts[col] += 1

    diet_entropy = entropy(collection_counts)
    mood_entropy = entropy(mood_counts)

    # ========== Humor Profile ==========
    humor_counts = Counter()
    sarcasm_values = []
    for p in posts:
        va = p.get("vision_analysis", {}) or {}
        humor_counts[safe_humor(va)] += 1
        sarcasm_values.append(safe_sarcasm(va))

    # Compile
    profile = {
        "panas": panas,
        "sessions": {
            "total_sessions": len(sessions),
            "mean_session_length": round(sum(session_lengths) / len(sessions), 1) if sessions else 0,
            "max_session_length": max(session_lengths) if session_lengths else 0,
            "median_session_length": sorted(session_lengths)[len(session_lengths)//2] if session_lengths else 0,
        },
        "behavior": {
            "peak_hour": hour_counts.most_common(1)[0][0] if hour_counts else 0,
            "peak_day": day_counts.most_common(1)[0][0] if day_counts else "",
            "hourly_distribution": dict(sorted(hour_counts.items())),
            "daily_distribution": dict(day_counts),
        },
        "information_diet": {
            "collection_entropy": round(diet_entropy, 3),
            "mood_entropy": round(mood_entropy, 3),
            "top_collections": [c for c, _ in collection_counts.most_common(10)],
            "top_moods": [m for m, _ in mood_counts.most_common(10)],
        },
        "humor": {
            "distribution": dict(humor_counts.most_common()),
            "mean_sarcasm": round(sum(sarcasm_values) / len(sarcasm_values), 2) if sarcasm_values else 0,
            "high_sarcasm_pct": round(sum(1 for v in sarcasm_values if v >= 3) / len(sarcasm_values) * 100, 1) if sarcasm_values else 0,
        },
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"Saved → {OUTPUT_PATH}")
    print(f"PANAS: +{panas['positive_affect']:.3f} / -{panas['negative_affect']:.3f} (ratio {panas['ratio']})")
    print(f"Sessions: {len(sessions)}, Mean length: {profile['sessions']['mean_session_length']}")
    print(f"Diet entropy: {diet_entropy:.3f}")


if __name__ == "__main__":
    main()
