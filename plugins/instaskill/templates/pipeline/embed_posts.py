"""
Phase 2: Embedding

Embeds all posts using sentence-transformers MiniLM (384-dim, multilingual).
Stores vectors as .npy and indexes in LanceDB for vector search.

Input: saved_posts.json (with final_explainer)
Output: data/embeddings.npy, data/post_ids.json, instagram_vectors/ (LanceDB)

Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim, 118M params)
Do NOT use nomic-ai/nomic-embed-text-v2-moe — 500x slower on Apple Silicon.
"""

import json
import sys
from pathlib import Path

import numpy as np

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
EMBEDDINGS_PATH = Path("data/embeddings.npy")
POST_IDS_PATH = Path("data/post_ids.json")
LANCEDB_PATH = Path("instagram_vectors")
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# =======================================


def get_text(post):
    """Extract searchable text from a post."""
    return (post.get("final_explainer", "") or post.get("text", "") or "")[:2000]


def main():
    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)
    print(f"Loaded {len(posts)} posts")

    if "--stats" in sys.argv:
        if EMBEDDINGS_PATH.exists():
            emb = np.load(EMBEDDINGS_PATH)
            print(f"Embeddings: {emb.shape}")
        return

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    print(f"Model: {MODEL_NAME} ({model.get_sentence_embedding_dimension()}D)")

    texts = [get_text(p) for p in posts]
    post_ids = [p["id"] for p in posts]

    print("Embedding...", flush=True)
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    embeddings = np.array(embeddings, dtype=np.float32)
    print(f"Shape: {embeddings.shape}")

    # Save raw embeddings
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_PATH, embeddings)
    print(f"Saved → {EMBEDDINGS_PATH}")

    with open(POST_IDS_PATH, "w") as f:
        json.dump(post_ids, f)
    print(f"Saved → {POST_IDS_PATH}")

    # Index in LanceDB (use pandas DataFrame, NOT raw dicts)
    import lancedb
    import pandas as pd

    db = lancedb.connect(str(LANCEDB_PATH))

    records = []
    for i, post in enumerate(posts):
        records.append({
            "id": post["id"],
            "text": get_text(post)[:2000],
            "mood": str((post.get("vision_analysis") or {}).get("mood", "")),
            "collection": str((post.get("collections") or [""])[0]),
            "vector": embeddings[i].tolist(),  # MUST be .tolist()
        })

    df = pd.DataFrame(records)
    table = db.create_table("posts", df, mode="overwrite")
    print(f"LanceDB indexed: {len(df)} records → {LANCEDB_PATH}/")


if __name__ == "__main__":
    main()
