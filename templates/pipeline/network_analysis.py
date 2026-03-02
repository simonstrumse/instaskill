"""
Phase 6: Network Analysis

Two networks:
  1. Account similarity: cosine similarity of account embedding centroids → Louvain communities
  2. Tag co-occurrence: vision_analysis.tags co-occurrence matrix → communities

Input: saved_posts.json, data/embeddings.npy
Output: data/account_network.json, data/tag_network.json
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from numpy.linalg import norm

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
EMBEDDINGS_PATH = Path("data/embeddings.npy")
ACCOUNT_NETWORK_PATH = Path("data/account_network.json")
TAG_NETWORK_PATH = Path("data/tag_network.json")

COSINE_THRESHOLD = 0.6      # Min similarity for account edges
MIN_TAG_COUNT = 10           # Min tag occurrences to include
MIN_EDGE_WEIGHT = 5          # Min co-occurrence for tag edges
MIN_ACCOUNT_POSTS = 3        # Min posts per account
# =======================================


def main():
    import networkx as nx
    from community import community_louvain

    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)
    embeddings = np.load(EMBEDDINGS_PATH)
    print(f"Posts: {len(posts)}, Embeddings: {embeddings.shape}")

    # ========== ACCOUNT NETWORK ==========
    print("\n--- Account Network ---")
    account_posts = defaultdict(list)
    for i, post in enumerate(posts):
        username = post.get("author", {}).get("username", "")
        if username and i < len(embeddings):
            account_posts[username].append(i)

    # Filter to accounts with enough posts
    accounts = {u: idx for u, idx in account_posts.items() if len(idx) >= MIN_ACCOUNT_POSTS}
    print(f"Accounts with >={MIN_ACCOUNT_POSTS} posts: {len(accounts)}")

    # Compute centroids
    centroids = {}
    for username, indices in accounts.items():
        centroids[username] = embeddings[indices].mean(axis=0)

    # Build similarity graph
    usernames = list(centroids.keys())
    G = nx.Graph()
    for u in usernames:
        G.add_node(u, post_count=len(accounts[u]))

    for i, u1 in enumerate(usernames):
        for u2 in usernames[i+1:]:
            sim = np.dot(centroids[u1], centroids[u2]) / (
                norm(centroids[u1]) * norm(centroids[u2]) + 1e-8
            )
            if sim >= COSINE_THRESHOLD:
                G.add_edge(u1, u2, weight=round(float(sim), 3))

    # Community detection
    communities = community_louvain.best_partition(G) if len(G.edges) > 0 else {}
    for node, comm in communities.items():
        G.nodes[node]["community"] = comm

    # Export
    account_data = {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes],
        "edges": [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)],
        "stats": {
            "total_accounts": len(accounts),
            "total_edges": len(G.edges),
            "communities": len(set(communities.values())) if communities else 0,
        },
    }
    with open(ACCOUNT_NETWORK_PATH, "w", encoding="utf-8") as f:
        json.dump(account_data, f, ensure_ascii=False, indent=2)
    print(f"Saved → {ACCOUNT_NETWORK_PATH}")

    # ========== TAG NETWORK ==========
    print("\n--- Tag Network ---")
    tag_counts = Counter()
    tag_cooccurrence = Counter()

    for post in posts:
        tags = (post.get("vision_analysis") or {}).get("tags", []) or []
        tags = [t.lower() for t in tags if isinstance(t, str)]
        for tag in tags:
            tag_counts[tag] += 1
        for i, t1 in enumerate(tags):
            for t2 in tags[i+1:]:
                pair = tuple(sorted([t1, t2]))
                tag_cooccurrence[pair] += 1

    # Filter
    valid_tags = {t for t, c in tag_counts.items() if c >= MIN_TAG_COUNT}
    print(f"Tags with >={MIN_TAG_COUNT} occurrences: {len(valid_tags)}")

    T = nx.Graph()
    for tag in valid_tags:
        T.add_node(tag, count=tag_counts[tag])

    for (t1, t2), weight in tag_cooccurrence.items():
        if t1 in valid_tags and t2 in valid_tags and weight >= MIN_EDGE_WEIGHT:
            T.add_edge(t1, t2, weight=weight)

    tag_communities = community_louvain.best_partition(T) if len(T.edges) > 0 else {}
    for node, comm in tag_communities.items():
        T.nodes[node]["community"] = comm

    tag_data = {
        "nodes": [{"id": n, **T.nodes[n]} for n in T.nodes],
        "edges": [{"source": u, "target": v, **d} for u, v, d in T.edges(data=True)],
        "stats": {
            "total_tags": len(valid_tags),
            "total_edges": len(T.edges),
            "communities": len(set(tag_communities.values())) if tag_communities else 0,
        },
    }
    with open(TAG_NETWORK_PATH, "w", encoding="utf-8") as f:
        json.dump(tag_data, f, ensure_ascii=False, indent=2)
    print(f"Saved → {TAG_NETWORK_PATH}")


if __name__ == "__main__":
    main()
