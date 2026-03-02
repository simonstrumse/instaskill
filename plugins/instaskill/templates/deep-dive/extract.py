"""
Step 1: Collection Subset Extraction

Filters posts belonging to your collection from saved_posts.json,
attaches existing analysis (embeddings, topics, sentiment, emotions),
computes double-save flags, and normalizes dates.

Output: {OUTPUT_DIR}/{slug}_posts.json + {slug}_embeddings.npy

Customize: Set COLLECTION_FILTER_NAMES and DOUBLE_SAVE_TARGETS in config.py
"""

import json
import sys
from datetime import datetime
import numpy as np

from config import (
    COLLECTION_FILTER_NAMES, COLLECTION_SLUG, DOUBLE_SAVE_TARGETS,
    POSTS_JSON, POST_IDS_JSON, EMBEDDINGS_NPY, TOPICS_JSON, SENTIMENT_JSON,
    OUTPUT_DIR, OUTPUT_POSTS, OUTPUT_EMBEDDINGS, OUTPUT_POST_IDS,
)


def load_all_data():
    """Load all source data files from the base pipeline."""
    print("Loading saved_posts.json...")
    with open(POSTS_JSON, "r", encoding="utf-8") as f:
        posts = json.load(f)
    print(f"  → {len(posts)} total posts")

    print("Loading post_ids.json...")
    with open(POST_IDS_JSON) as f:
        post_ids = json.load(f)
    print(f"  → {len(post_ids)} post IDs (embedding index)")

    print("Loading embeddings.npy...")
    embeddings = np.load(EMBEDDINGS_NPY)
    print(f"  → shape {embeddings.shape}")

    print("Loading topic_assignments.json...")
    with open(TOPICS_JSON) as f:
        topics = json.load(f)
    print(f"  → {len(topics)} topic assignments")

    print("Loading sentiment_scores.json...")
    with open(SENTIMENT_JSON) as f:
        sentiment = json.load(f)
    print(f"  → {len(sentiment)} sentiment scores")

    return posts, post_ids, embeddings, topics, sentiment


def filter_collection(posts):
    """Filter posts belonging to this collection."""
    collection_posts = []
    for post in posts:
        collections = post.get("collections") or []
        if any(name in collections for name in COLLECTION_FILTER_NAMES):
            collection_posts.append(post)
    return collection_posts


def build_id_index(post_ids):
    """Build post_id → embedding index mapping."""
    return {pid: i for i, pid in enumerate(post_ids)}


def attach_analysis(posts, id_to_idx, embeddings, topics, sentiment):
    """Attach topic and sentiment data to each post. Returns posts + subset embeddings."""
    # Build lookups
    topic_map = {t["post_id"]: t for t in topics} if isinstance(topics, list) else {}
    if isinstance(topics, dict) and "assignments" in topics:
        topic_map = {t["post_id"]: t for t in topics["assignments"]}

    sentiment_map = {}
    if isinstance(sentiment, list):
        sentiment_map = {s["post_id"]: s for s in sentiment}
    elif isinstance(sentiment, dict):
        sentiment_map = sentiment  # Already keyed by post_id

    subset_indices = []
    enriched = []

    for post in posts:
        pid = post["id"]
        idx = id_to_idx.get(pid)
        if idx is not None:
            subset_indices.append(idx)

        # Attach topic
        topic = topic_map.get(pid, {})
        post["topic_id"] = topic.get("topic_id", topic.get("topic", -1))
        post["topic_label"] = topic.get("topic_label", topic.get("label", "Unknown"))

        # Attach sentiment
        sent = sentiment_map.get(pid, {})
        post["sentiment_stars"] = sent.get("stars", sent.get("sentiment_stars", 3))
        post["emotions"] = sent.get("emotions", sent.get("emotion_scores", {}))
        post["dominant_emotion"] = sent.get("dominant_emotion", "neutral")

        # Normalize dates
        date_str = post.get("saved_on") or post.get("created_at", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                post["day"] = dt.strftime("%Y-%m-%d")
                post["month"] = dt.strftime("%Y-%m")
                post["week"] = dt.strftime("%Y-W%V")
            except (ValueError, TypeError):
                post["day"] = date_str[:10]
                post["month"] = date_str[:7]
                post["week"] = ""

        enriched.append(post)

    # Build subset embeddings
    if subset_indices:
        subset_embeddings = embeddings[subset_indices]
    else:
        subset_embeddings = np.array([])

    return enriched, subset_embeddings


def compute_double_save_flags(posts, all_posts):
    """Flag posts that appear in other collections (cross-collection overlap)."""
    if not DOUBLE_SAVE_TARGETS:
        return posts

    # Build lookup: post_id → collections
    all_collections = {p["id"]: p.get("collections", []) for p in all_posts}

    for post in posts:
        pid = post["id"]
        post_collections = all_collections.get(pid, [])
        for label, target_name in DOUBLE_SAVE_TARGETS.items():
            post[f"is_{label}_double_save"] = target_name in post_collections

    return posts


def main():
    posts, post_ids, embeddings, topics, sentiment = load_all_data()
    id_to_idx = build_id_index(post_ids)

    # Filter
    collection_posts = filter_collection(posts)
    print(f"\n{COLLECTION_SLUG}: {len(collection_posts)} posts")

    if not collection_posts:
        print("ERROR: No posts found. Check COLLECTION_FILTER_NAMES in config.py")
        sys.exit(1)

    # Enrich
    enriched, subset_embeddings = attach_analysis(
        collection_posts, id_to_idx, embeddings, topics, sentiment
    )

    # Cross-collection flags
    enriched = compute_double_save_flags(enriched, posts)

    # Stats
    accounts = set(p.get("author", {}).get("username", "") for p in enriched)
    dates = sorted(p.get("day", "") for p in enriched if p.get("day"))
    print(f"  Accounts: {len(accounts)}")
    print(f"  Date range: {dates[0] if dates else '?'} → {dates[-1] if dates else '?'}")
    for label in DOUBLE_SAVE_TARGETS:
        count = sum(1 for p in enriched if p.get(f"is_{label}_double_save"))
        print(f"  Double-saved to {label}: {count}")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_POSTS, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(enriched)} posts → {OUTPUT_POSTS}")

    if subset_embeddings.size > 0:
        np.save(OUTPUT_EMBEDDINGS, subset_embeddings)
        print(f"Saved embeddings → {OUTPUT_EMBEDDINGS} (shape {subset_embeddings.shape})")

    # Save post IDs for embedding index mapping
    subset_ids = [p["id"] for p in enriched if id_to_idx.get(p["id"]) is not None]
    with open(OUTPUT_POST_IDS, "w", encoding="utf-8") as f:
        json.dump(subset_ids, f)
    print(f"Saved {len(subset_ids)} post IDs → {OUTPUT_POST_IDS}")


if __name__ == "__main__":
    main()
