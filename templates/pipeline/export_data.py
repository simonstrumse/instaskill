"""
Phase 9b: Data Export

Exports enriched posts + analysis results to CSV and JSON for external use.
Merges topics, sentiment, and UMAP coordinates into a single enriched JSON.

Input:  data/instagram/saved_posts.json + data/topic_assignments.json +
        data/sentiment_scores.json + data/umap_2d.npy + data/post_ids.json
Output: data/exports/posts_full.csv, posts_enriched.json, accounts.csv, topics.csv

Customize: All *_PATH constants at top
"""

import csv
import json
import os

# ── Configuration ──────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
EXPORTS = os.path.join(DATA, "exports")

INPUT_PATH = os.path.join(DATA, "instagram", "saved_posts.json")
TOPIC_PATH = os.path.join(DATA, "topic_assignments.json")
SENTIMENT_PATH = os.path.join(DATA, "sentiment_scores.json")
TOPICS_SUMMARY_PATH = os.path.join(DATA, "topics_summary.json")
UMAP_2D_PATH = os.path.join(DATA, "umap_2d.npy")
POST_IDS_PATH = os.path.join(DATA, "post_ids.json")
# ───────────────────────────────────────────────────────────────────────────

os.makedirs(EXPORTS, exist_ok=True)


def load_keyed(path, key="post_id"):
    """Load a JSON file and normalize to a dict keyed by `key`.
    Upstream writes lists of {post_id, ...}; this converts to {post_id: item}."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return {item[key]: item for item in raw if key in item}
    return raw


def load_all():
    """Load posts + all analysis outputs, returning merged lookup dicts."""
    print("Loading all data...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)

    topics = load_keyed(TOPIC_PATH)
    sentiments = load_keyed(SENTIMENT_PATH)

    umap_coords = {}
    if os.path.exists(UMAP_2D_PATH) and os.path.exists(POST_IDS_PATH):
        import numpy as np
        coords = np.load(UMAP_2D_PATH)
        with open(POST_IDS_PATH) as f:
            ids = json.load(f)
        for i, pid in enumerate(ids):
            umap_coords[pid] = (float(coords[i, 0]), float(coords[i, 1]))

    topics_summary = []
    if os.path.exists(TOPICS_SUMMARY_PATH):
        with open(TOPICS_SUMMARY_PATH) as f:
            topics_summary = json.load(f)

    return posts, topics, sentiments, umap_coords, topics_summary


def export_posts_csv(posts, topics, sentiments, umap_coords):
    """Export flat CSV with one row per post."""
    path = os.path.join(EXPORTS, "posts_full.csv")
    fields = [
        "id", "username", "text_preview", "created_at",
        "collections", "media_type", "mood", "tone",
        "topic_id", "topic_label", "sentiment_stars",
        "dominant_emotion", "umap_x", "umap_y",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for post in posts:
            pid = post.get("id", "")
            va = post.get("vision_analysis", {})
            topic_info = topics.get(pid, {})
            sent_info = sentiments.get(pid, {})
            coords = umap_coords.get(pid, (None, None))

            writer.writerow({
                "id": pid,
                "username": post.get("author", {}).get("username", ""),
                "text_preview": (post.get("text", "") or "")[:200],
                "created_at": post.get("created_at", ""),
                "collections": "|".join(post.get("collections", [])),
                "media_type": post.get("media", [{}])[0].get("type", "") if post.get("media") else "",
                "mood": va.get("mood", ""),
                "tone": va.get("tone", ""),
                "topic_id": topic_info.get("topic_id", -1),
                "topic_label": topic_info.get("topic_label", ""),
                "sentiment_stars": sent_info.get("stars", ""),
                "dominant_emotion": sent_info.get("dominant_emotion", ""),
                "umap_x": coords[0],
                "umap_y": coords[1],
            })

    print(f"  posts_full.csv: {len(posts)} rows")


def export_posts_enriched(posts, topics, sentiments, umap_coords):
    """Export full enriched JSON with all analysis merged per post."""
    path = os.path.join(EXPORTS, "posts_enriched.json")
    enriched = []

    for post in posts:
        pid = post.get("id", "")
        entry = dict(post)
        entry["_topic"] = topics.get(pid, {})
        entry["_sentiment"] = sentiments.get(pid, {})
        coords = umap_coords.get(pid)
        if coords:
            entry["_umap"] = {"x": coords[0], "y": coords[1]}
        enriched.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False)

    print(f"  posts_enriched.json: {len(enriched)} posts")


def export_accounts_csv(posts, sentiments):
    """Export per-account summary statistics."""
    path = os.path.join(EXPORTS, "accounts.csv")
    from collections import Counter, defaultdict

    account_posts = defaultdict(list)
    for post in posts:
        username = post.get("author", {}).get("username", "unknown")
        account_posts[username].append(post)

    fields = ["username", "post_count", "collections", "avg_sentiment", "date_range"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for username, user_posts in sorted(account_posts.items(), key=lambda x: -len(x[1])):
            colls = set()
            stars = []
            dates = []
            for p in user_posts:
                colls.update(p.get("collections", []))
                s = sentiments.get(p.get("id", ""), {}).get("stars")
                if s:
                    stars.append(float(s))
                d = p.get("created_at", "")
                if d:
                    dates.append(d)

            writer.writerow({
                "username": username,
                "post_count": len(user_posts),
                "collections": "|".join(sorted(colls)),
                "avg_sentiment": round(sum(stars) / len(stars), 2) if stars else "",
                "date_range": f"{min(dates)[:10]}..{max(dates)[:10]}" if dates else "",
            })

    print(f"  accounts.csv: {len(account_posts)} accounts")


def export_topics_csv(topics_summary):
    """Export topic summary table."""
    path = os.path.join(EXPORTS, "topics.csv")
    if not topics_summary:
        print("  topics.csv: skipped (no topics_summary.json)")
        return

    fields = ["topic_id", "label", "count", "top_words"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for topic in topics_summary:
            writer.writerow({
                "topic_id": topic.get("topic_id", ""),
                "label": topic.get("label", ""),
                "count": topic.get("count", 0),
                "top_words": ", ".join(topic.get("top_words", [])[:10]),
            })

    print(f"  topics.csv: {len(topics_summary)} topics")


def main():
    posts, topics, sentiments, umap_coords, topics_summary = load_all()
    print(f"\nExporting {len(posts)} posts to {EXPORTS}/")

    export_posts_csv(posts, topics, sentiments, umap_coords)
    export_posts_enriched(posts, topics, sentiments, umap_coords)
    export_accounts_csv(posts, sentiments)
    export_topics_csv(topics_summary)

    print(f"\nDone. All exports in {EXPORTS}/")


if __name__ == "__main__":
    main()
