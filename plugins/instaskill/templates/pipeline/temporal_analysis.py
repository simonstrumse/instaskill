"""
Phase 7: Temporal Analysis

Computes temporal patterns: daily volume, topic shifts, sentiment trajectory,
interest drift (Jensen-Shannon divergence), burst detection, collection growth.

Input: saved_posts.json, topic_assignments.json, sentiment_scores.json
Output: data/temporal_patterns.json
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
TOPICS_PATH = Path("data/topic_assignments.json")
SENTIMENT_PATH = Path("data/sentiment_scores.json")
OUTPUT_PATH = Path("data/temporal_patterns.json")
ROLLING_WINDOW = 30  # Days for rolling averages
Z_THRESHOLD = 2.0    # Burst detection threshold
# =======================================


def js_divergence(p, q):
    """Jensen-Shannon divergence between two distributions."""
    from scipy.spatial.distance import jensenshannon
    return float(jensenshannon(p, q) ** 2)


def main():
    with open(POSTS_PATH) as f:
        posts = json.load(f)
    with open(TOPICS_PATH) as f:
        topics = json.load(f)
    with open(SENTIMENT_PATH) as f:
        sentiment = json.load(f)

    topic_map = {t["post_id"]: t for t in topics if "post_id" in t} if isinstance(topics, list) else {}
    sent_map = {s["post_id"]: s for s in sentiment if "post_id" in s} if isinstance(sentiment, list) else sentiment

    print(f"Posts: {len(posts)}, Topics: {len(topic_map)}, Sentiment: {len(sent_map)}")

    # Daily volume
    daily = Counter()
    for p in posts:
        day = p.get("saved_on", p.get("created_at", ""))[:10]
        if day:
            daily[day] += 1

    # Monthly topic distribution
    monthly_topics = defaultdict(Counter)
    for p in posts:
        month = p.get("saved_on", p.get("created_at", ""))[:7]
        topic = topic_map.get(p["id"], {}).get("topic_id", -1)
        monthly_topics[month][topic] += 1

    # Monthly sentiment
    monthly_sentiment = defaultdict(list)
    monthly_emotions = defaultdict(lambda: defaultdict(float))
    for p in posts:
        month = p.get("saved_on", p.get("created_at", ""))[:7]
        sent = sent_map.get(p["id"], {})
        monthly_sentiment[month].append(sent.get("stars", 3))
        for emo, score in sent.get("emotions", {}).items():
            monthly_emotions[month][emo] += score

    # Interest drift (JSD between consecutive months)
    months = sorted(monthly_topics.keys())
    all_topics = set()
    for counts in monthly_topics.values():
        all_topics.update(counts.keys())
    all_topics = sorted(all_topics)

    drift = []
    for i in range(1, len(months)):
        p = np.array([monthly_topics[months[i-1]].get(t, 0) for t in all_topics], dtype=float)
        q = np.array([monthly_topics[months[i]].get(t, 0) for t in all_topics], dtype=float)
        if p.sum() > 0 and q.sum() > 0:
            p /= p.sum()
            q /= q.sum()
            drift.append({
                "from": months[i-1], "to": months[i],
                "jsd": round(js_divergence(p, q), 4),
            })

    # Burst detection
    sorted_days = sorted(daily.keys())
    values = [daily[d] for d in sorted_days]
    arr = np.array(values, dtype=float)
    mean, std = arr.mean(), arr.std()
    bursts = []
    if std > 0:
        zscores = (arr - mean) / std
        for i, (day, z) in enumerate(zip(sorted_days, zscores)):
            if z >= Z_THRESHOLD:
                bursts.append({"date": day, "count": int(values[i]), "zscore": round(float(z), 2)})

    # Collection growth
    collections = defaultdict(Counter)
    for p in posts:
        month = p.get("saved_on", p.get("created_at", ""))[:7]
        for col in (p.get("collections") or []):
            collections[col][month] += 1

    growth = {col: dict(sorted(months.items())) for col, months in collections.items()}

    # Compile
    output = {
        "daily_volume": dict(sorted(daily.items())),
        "monthly_topics": {m: dict(c) for m, c in sorted(monthly_topics.items())},
        "monthly_sentiment": {
            m: {"mean_stars": round(np.mean(v), 2), "count": len(v)}
            for m, v in sorted(monthly_sentiment.items())
        },
        "monthly_emotions": {
            m: {k: round(v / max(len(monthly_sentiment.get(m, [])), 1), 4) for k, v in emos.items()}
            for m, emos in sorted(monthly_emotions.items())
        },
        "interest_drift": drift,
        "bursts": bursts,
        "collection_growth": growth,
        "stats": {
            "total_days": len(daily),
            "total_months": len(months),
            "total_bursts": len(bursts),
            "mean_daily": round(mean, 1),
            "max_daily": int(max(values)) if values else 0,
        },
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved → {OUTPUT_PATH}")
    print(f"Days: {len(daily)}, Months: {len(months)}, Bursts: {len(bursts)}")


if __name__ == "__main__":
    main()
