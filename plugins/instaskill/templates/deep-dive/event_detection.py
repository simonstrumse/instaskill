"""
Step 3: Event Detection

Detects significant temporal events using three complementary methods:
  1. Ruptures PELT — changepoint detection for structural breaks
  2. Z-score — anomaly detection for spike events
  3. Kleinberg — hierarchical burst model for sustained activity

Each detected event is fingerprinted with emotion signature, frame distribution,
top entities, and top accounts.

Output: {OUTPUT_DIR}/{slug}_events.json

Customize: EVENT_AGGREGATION, EVENT_Z_THRESHOLD, EVENT_PELT_PENALTY in config.py
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np

from config import (
    COLLECTION_SLUG, EVENT_AGGREGATION, EVENT_Z_THRESHOLD,
    EVENT_PELT_PENALTY, EVENT_CONTEXT_WINDOW, OUTPUT_DIR, OUTPUT_POSTS,
)


def load_posts():
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        return json.load(f)


def build_time_series(posts, aggregation="daily"):
    """Build post count time series at daily or weekly granularity."""
    counts = Counter()
    for post in posts:
        if aggregation == "weekly":
            key = post.get("week", "")
        else:
            key = post.get("day", "")
        if key:
            counts[key] += 1

    if not counts:
        return [], []

    periods = sorted(counts.keys())

    # Fill gaps for daily aggregation
    if aggregation == "daily" and len(periods) >= 2:
        start = datetime.strptime(periods[0], "%Y-%m-%d")
        end = datetime.strptime(periods[-1], "%Y-%m-%d")
        all_days = []
        d = start
        while d <= end:
            all_days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        periods = all_days

    values = [counts.get(p, 0) for p in periods]
    return periods, values


def detect_zscore_bursts(periods, values, threshold):
    """Detect events where z-score exceeds threshold."""
    arr = np.array(values, dtype=float)
    if len(arr) < 3:
        return []

    mean = arr.mean()
    std = arr.std()
    if std == 0:
        return []

    zscores = (arr - mean) / std
    events = []
    for i, (period, val, z) in enumerate(zip(periods, values, zscores)):
        if z >= threshold:
            events.append({
                "period": period,
                "postCount": int(val),
                "zScore": round(float(z), 3),
                "method": "zscore",
            })
    return events


def detect_pelt_changepoints(values, penalty):
    """Detect structural changepoints using Ruptures PELT algorithm."""
    try:
        import ruptures as rpt
    except ImportError:
        print("  [PELT skipped: pip install ruptures]")
        return []

    arr = np.array(values, dtype=float).reshape(-1, 1)
    if len(arr) < 10:
        return []

    algo = rpt.Pelt(model="rbf", min_size=3).fit(arr)
    changepoints = algo.predict(pen=penalty)
    # Remove the last index (always == len)
    return [cp for cp in changepoints if cp < len(values)]


def detect_kleinberg_bursts(values, s=2, gamma=1.0):
    """Detect bursts using Kleinberg's automaton model."""
    try:
        # Simplified Kleinberg: identify periods where rate exceeds s * baseline
        arr = np.array(values, dtype=float)
        baseline = arr.mean()
        if baseline == 0:
            return []

        burst_threshold = s * baseline
        bursts = []
        in_burst = False
        burst_start = None

        for i, val in enumerate(arr):
            if val >= burst_threshold and not in_burst:
                in_burst = True
                burst_start = i
            elif val < burst_threshold and in_burst:
                in_burst = False
                bursts.append((burst_start, i - 1))

        if in_burst:
            bursts.append((burst_start, len(arr) - 1))

        return bursts
    except Exception:
        return []


def classify_burst_shape(values_window):
    """Classify the shape of a burst: point, sharp_spike, front_loaded, build_up, sustained."""
    if len(values_window) <= 1:
        return "point"

    peak_idx = np.argmax(values_window)
    total = sum(values_window)

    if len(values_window) <= 3:
        return "sharp_spike"

    first_half = sum(values_window[:len(values_window)//2])
    if first_half / total > 0.7:
        return "front_loaded"
    elif first_half / total < 0.3:
        return "build_up"
    else:
        return "sustained"


def fingerprint_events(events, posts, periods, context_window):
    """Enrich each event with emotion, frame, entity, and account context."""
    # Build period → posts lookup
    posts_by_period = defaultdict(list)
    for post in posts:
        key = post.get("day", "") if EVENT_AGGREGATION == "daily" else post.get("week", "")
        if key:
            posts_by_period[key].append(post)

    # Period index for context window
    period_idx = {p: i for i, p in enumerate(periods)}

    for event in events:
        period = event["period"]
        idx = period_idx.get(period, -1)

        # Gather posts in context window
        context_posts = []
        if idx >= 0:
            for offset in range(-context_window, context_window + 1):
                neighbor_idx = idx + offset
                if 0 <= neighbor_idx < len(periods):
                    context_posts.extend(posts_by_period.get(periods[neighbor_idx], []))

        if not context_posts:
            context_posts = posts_by_period.get(period, [])

        n = len(context_posts)
        if n == 0:
            continue

        # Emotion signature
        emotions = defaultdict(float)
        for p in context_posts:
            for emo, score in (p.get("emotions", {}) or {}).items():
                emotions[emo] += score
        event["emotionSignature"] = {
            k: round(v / n, 4) for k, v in sorted(emotions.items(), key=lambda x: -x[1])
        }

        # Top accounts
        accounts = Counter(p.get("author", {}).get("username", "") for p in context_posts)
        event["topAccounts"] = [a for a, _ in accounts.most_common(5) if a]

        # Top topics
        topics = Counter(p.get("topic_label", "Unknown") for p in context_posts)
        event["topTopics"] = [
            {"label": t, "count": c}
            for t, c in topics.most_common(5) if t != "Unknown"
        ]

        # Dominant emotion
        if event.get("emotionSignature"):
            event["dominantEmotion"] = max(
                event["emotionSignature"], key=event["emotionSignature"].get
            )

    return events


def main():
    posts = load_posts()
    print(f"Loaded {len(posts)} posts")
    print(f"Aggregation: {EVENT_AGGREGATION}, Z-threshold: {EVENT_Z_THRESHOLD}")

    periods, values = build_time_series(posts, EVENT_AGGREGATION)
    print(f"Time series: {len(periods)} periods, total count {sum(values)}")

    # Method 1: Z-score
    zscore_events = detect_zscore_bursts(periods, values, EVENT_Z_THRESHOLD)
    print(f"  Z-score events: {len(zscore_events)}")

    # Method 2: PELT changepoints
    changepoints = detect_pelt_changepoints(values, EVENT_PELT_PENALTY)
    print(f"  PELT changepoints: {len(changepoints)}")

    # Method 3: Kleinberg bursts
    kleinberg = detect_kleinberg_bursts(values)
    print(f"  Kleinberg bursts: {len(kleinberg)}")

    # Merge z-score events with changepoint context
    cp_set = set(changepoints)
    for event in zscore_events:
        idx = periods.index(event["period"]) if event["period"] in periods else -1
        event["isChangepoint"] = idx in cp_set or (idx + 1) in cp_set or (idx - 1) in cp_set

    # Add Kleinberg burst info
    for event in zscore_events:
        idx = periods.index(event["period"]) if event["period"] in periods else -1
        for burst_start, burst_end in kleinberg:
            if burst_start <= idx <= burst_end:
                burst_values = values[burst_start:burst_end+1]
                event["burstType"] = classify_burst_shape(burst_values)
                event["burstDuration"] = burst_end - burst_start + 1
                break
        if "burstType" not in event:
            event["burstType"] = "point"

    # Fingerprint all events
    events = fingerprint_events(zscore_events, posts, periods, EVENT_CONTEXT_WINDOW)

    # Assign event IDs
    for i, event in enumerate(events):
        event["eventId"] = f"evt_{i+1:03d}"

    print(f"\nFinal events: {len(events)}")
    for e in events[:10]:
        print(f"  {e['eventId']} | {e['period']} | z={e['zScore']:.1f} | "
              f"{e['postCount']} posts | {e.get('burstType', '?')} | "
              f"{e.get('dominantEmotion', '?')}")

    # Save
    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_events.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "events": events,
            "time_series": {"periods": periods, "values": values},
            "changepoints": changepoints,
            "kleinberg_bursts": [{"start": s, "end": e} for s, e in kleinberg],
            "config": {
                "aggregation": EVENT_AGGREGATION,
                "z_threshold": EVENT_Z_THRESHOLD,
                "pelt_penalty": EVENT_PELT_PENALTY,
            },
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    main()
