"""
Phase 4: Topic Modeling

BERTopic with pre-computed embeddings. Uses HDBSCAN for clustering and
CountVectorizer for topic representation.

Input: data/embeddings.npy, saved_posts.json
Output: data/topic_assignments.json, data/topics_summary.json, data/bertopic_model/
"""

import json
from pathlib import Path

import numpy as np

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
EMBEDDINGS_PATH = Path("data/embeddings.npy")
TOPICS_PATH = Path("data/topic_assignments.json")
SUMMARY_PATH = Path("data/topics_summary.json")
MODEL_PATH = Path("data/bertopic_model")

HDBSCAN_MIN_CLUSTER = 15
HDBSCAN_MIN_SAMPLES = 5
VECTORIZER_STOP_WORDS = "english"
VECTORIZER_MIN_DF = 5
VECTORIZER_MAX_DF = 0.95
VECTORIZER_NGRAM = (1, 2)
NR_TOPICS = "auto"  # Set int for fixed topic count
# =======================================


def get_text(post):
    return (post.get("final_explainer", "") or post.get("text", "") or "")[:2000]


def main():
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer

    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)

    embeddings = np.load(EMBEDDINGS_PATH)
    texts = [get_text(p) for p in posts]
    print(f"Posts: {len(posts)}, Embeddings: {embeddings.shape}")

    hdbscan = HDBSCAN(
        min_cluster_size=HDBSCAN_MIN_CLUSTER,
        min_samples=HDBSCAN_MIN_SAMPLES,
        metric="euclidean",
        prediction_data=True,
    )

    vectorizer = CountVectorizer(
        stop_words=VECTORIZER_STOP_WORDS,
        min_df=VECTORIZER_MIN_DF,
        max_df=VECTORIZER_MAX_DF,
        ngram_range=VECTORIZER_NGRAM,
    )

    topic_model = BERTopic(
        hdbscan_model=hdbscan,
        vectorizer_model=vectorizer,
        nr_topics=NR_TOPICS,
        verbose=True,
    )

    topics, probs = topic_model.fit_transform(texts, embeddings)
    print(f"Topics found: {len(set(topics)) - (1 if -1 in topics else 0)}")
    print(f"Outliers (topic -1): {topics.count(-1)} ({topics.count(-1)/len(topics)*100:.0f}%)")

    # Topic assignments
    assignments = []
    for i, (post, topic_id) in enumerate(zip(posts, topics)):
        label = "Unknown"
        if topic_id >= 0:
            info = topic_model.get_topic(topic_id)
            label = ", ".join(w for w, _ in info[:3]) if info else f"Topic {topic_id}"
        assignments.append({
            "post_id": post["id"],
            "topic_id": int(topic_id),
            "topic_label": label,
        })

    with open(TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(assignments, f, ensure_ascii=False, indent=2)
    print(f"Saved → {TOPICS_PATH}")

    # Topic summary
    topic_info = topic_model.get_topic_info()
    summary = []
    for _, row in topic_info.iterrows():
        if row["Topic"] == -1:
            continue
        summary.append({
            "topic_id": int(row["Topic"]),
            "count": int(row["Count"]),
            "name": row.get("Name", f"Topic {row['Topic']}"),
            "representation": [w for w, _ in topic_model.get_topic(row["Topic"])[:10]],
        })

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved → {SUMMARY_PATH}")

    # Save model
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    topic_model.save(str(MODEL_PATH))
    print(f"Model → {MODEL_PATH}/")


if __name__ == "__main__":
    main()
