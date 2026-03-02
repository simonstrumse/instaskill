"""
Step 4: Account Classification

Classifies Instagram accounts into domain-specific types using LLM discovery.
Top N accounts are classified by Claude subagent; remaining accounts use
cosine similarity to type centroids.

This is a DISCOVERY step — the types should emerge from YOUR data, not be
copied from another collection.

Output: {OUTPUT_DIR}/{slug}_accounts.json

Customize: ACCOUNT_TYPES and ACCOUNT_LLM_TOP_N in config.py
"""

import json
from collections import Counter, defaultdict

import numpy as np

from config import (
    COLLECTION_SLUG, ACCOUNT_TYPES, ACCOUNT_LLM_TOP_N,
    OUTPUT_DIR, OUTPUT_POSTS, OUTPUT_EMBEDDINGS,
)


def load_data():
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        posts = json.load(f)
    embeddings = np.load(OUTPUT_EMBEDDINGS) if OUTPUT_EMBEDDINGS.exists() else None
    return posts, embeddings


def build_account_stats(posts):
    """Group posts by account and compute per-account statistics."""
    accounts = defaultdict(lambda: {
        "posts": [], "emotions": defaultdict(float), "months": Counter(),
        "topics": Counter(), "sample_texts": [],
    })

    for post in posts:
        username = post.get("author", {}).get("username", "")
        if not username:
            continue

        acct = accounts[username]
        acct["posts"].append(post)

        for emo, score in (post.get("emotions", {}) or {}).items():
            acct["emotions"][emo] += score

        month = post.get("month", "")
        if month:
            acct["months"][month] += 1

        topic = post.get("topic_label", "")
        if topic and topic != "Unknown":
            acct["topics"][topic] += 1

        text = (post.get("final_explainer", "") or "")[:200]
        if text and len(acct["sample_texts"]) < 5:
            acct["sample_texts"].append(text)

    return dict(accounts)


def compute_account_embeddings(accounts, posts, embeddings):
    """Compute centroid embedding per account."""
    if embeddings is None:
        return {}

    # Build post_id → embedding index
    id_to_idx = {}
    for i, post in enumerate(posts):
        if i < len(embeddings):
            id_to_idx[post["id"]] = i

    centroids = {}
    for username, acct in accounts.items():
        indices = [id_to_idx[p["id"]] for p in acct["posts"] if p["id"] in id_to_idx]
        if indices:
            centroid = embeddings[indices].mean(axis=0)
            centroids[username] = centroid

    return centroids


def classify_top_accounts_prompt(accounts, top_n, account_types):
    """Build a prompt for Claude subagent to classify top accounts."""
    sorted_accounts = sorted(
        accounts.items(), key=lambda x: -len(x[1]["posts"])
    )[:top_n]

    lines = [
        "Classify each Instagram account into exactly one type based on their posting behavior.",
        f"\nAvailable types: {', '.join(account_types)}",
        "\nAccounts to classify:\n",
    ]

    for username, acct in sorted_accounts:
        n = len(acct["posts"])
        top_topics = [t for t, _ in acct["topics"].most_common(3)]
        top_emo = sorted(acct["emotions"].items(), key=lambda x: -x[1])[:2]
        emo_str = ", ".join(f"{e}" for e, _ in top_emo)
        sample = acct["sample_texts"][0][:150] if acct["sample_texts"] else ""

        lines.append(f"@{username} ({n} posts)")
        lines.append(f"  Topics: {', '.join(top_topics)}")
        lines.append(f"  Emotions: {emo_str}")
        lines.append(f"  Sample: \"{sample}\"")
        lines.append("")

    lines.append("\nRespond as JSON: [{\"username\": \"...\", \"type\": \"...\", \"role\": \"original_source|amplifier\"}]")
    return "\n".join(lines)


def classify_remaining_by_similarity(accounts, centroids, type_centroids, classified):
    """Classify unclassified accounts by cosine similarity to type centroids."""
    from numpy.linalg import norm

    results = {}
    for username, acct in accounts.items():
        if username in classified:
            continue
        if username not in centroids:
            results[username] = {"type": "other", "role": "amplifier", "method": "default"}
            continue

        vec = centroids[username]
        best_type = "other"
        best_sim = -1

        for type_name, type_centroid in type_centroids.items():
            sim = np.dot(vec, type_centroid) / (norm(vec) * norm(type_centroid) + 1e-8)
            if sim > best_sim:
                best_sim = sim
                best_type = type_name

        # Determine role based on content diversity
        role = "amplifier"
        if username in centroids and len(acct["posts"]) >= 3:
            # Simple heuristic: accounts with diverse content are original sources
            if len(acct["topics"]) >= 3:
                role = "original_source"

        results[username] = {
            "type": best_type,
            "role": role,
            "similarity": round(float(best_sim), 3),
            "method": "centroid_similarity",
        }

    return results


def build_output(accounts, classifications):
    """Build final account profiles."""
    results = []
    for username, acct in accounts.items():
        cls = classifications.get(username, {"type": "other", "role": "amplifier"})
        n = len(acct["posts"])

        # Normalize emotions
        emotion_profile = {}
        if acct["emotions"] and n > 0:
            emotion_profile = {
                k: round(v / n, 4)
                for k, v in sorted(acct["emotions"].items(), key=lambda x: -x[1])
            }

        dates = sorted(p.get("day", "") for p in acct["posts"] if p.get("day"))

        results.append({
            "username": username,
            "postCount": n,
            "accountType": cls.get("type", "other"),
            "accountRole": cls.get("role", "amplifier"),
            "community": "",  # Populated by network analysis if available
            "emotionProfile": emotion_profile,
            "activeMonths": sorted(acct["months"].keys()),
            "topTopics": [t for t, _ in acct["topics"].most_common(5)],
            "firstSeen": dates[0] if dates else "",
            "lastSeen": dates[-1] if dates else "",
            "classificationMethod": cls.get("method", "unknown"),
        })

    results.sort(key=lambda r: -r["postCount"])
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Classify Instagram accounts")
    parser.add_argument("command", nargs="?", default="discover",
                        choices=["discover", "merge"],
                        help="discover: generate LLM prompt; merge: apply LLM results + similarity")
    parser.add_argument("--llm-results", type=str, default=None,
                        help="Path to JSON file with LLM classification results (for merge)")
    args = parser.parse_args()

    posts, embeddings = load_data()
    print(f"Loaded {len(posts)} posts")

    accounts = build_account_stats(posts)
    print(f"Found {len(accounts)} unique accounts")

    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_accounts.json"

    if args.command == "discover":
        # Step 1: Discovery — show top accounts and generate LLM prompt
        print(f"\n--- DISCOVERY MODE ---")
        print(f"Top 20 accounts by post count:")
        for username, acct in sorted(accounts.items(), key=lambda x: -len(x[1]["posts"]))[:20]:
            topics = [t for t, _ in acct["topics"].most_common(3)]
            print(f"  @{username:30s} {len(acct['posts']):4d} posts  topics: {', '.join(topics)}")

        print(f"\nCurrent types: {ACCOUNT_TYPES}")
        print(f"Review the accounts above. Update ACCOUNT_TYPES in config.py if needed.")

        prompt = classify_top_accounts_prompt(accounts, ACCOUNT_LLM_TOP_N, ACCOUNT_TYPES)
        prompt_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_account_classification_prompt.txt"
        with open(prompt_path, "w") as f:
            f.write(prompt)
        print(f"\nClassification prompt saved → {prompt_path}")
        print(f"Feed this to a Claude subagent, save the JSON response, then run:")
        print(f"  python account_classification.py merge --llm-results <response.json>")

    elif args.command == "merge":
        # Step 2: Merge LLM results + classify remaining by cosine similarity
        llm_path = args.llm_results
        if not llm_path:
            # Look for default location
            llm_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_llm_classifications.json"
            if not llm_path.exists():
                print("ERROR: No --llm-results provided and no default file found.")
                print(f"Expected: {llm_path}")
                print("Run 'discover' first, feed the prompt to a subagent, save the response.")
                return

        with open(llm_path, "r", encoding="utf-8") as f:
            llm_results = json.load(f)

        # Build classification dict from LLM results
        classified = {}
        for item in llm_results:
            username = item.get("username", "").lstrip("@")
            if username:
                classified[username] = {
                    "type": item.get("type", "other"),
                    "role": item.get("role", "amplifier"),
                    "method": "llm_subagent",
                }
        print(f"LLM classified: {len(classified)} accounts")

        # Compute centroids and classify remaining by similarity
        centroids = compute_account_embeddings(accounts, posts, embeddings)

        # Build type centroids from LLM-classified accounts
        type_embeddings = {}
        for username, cls in classified.items():
            acct_type = cls["type"]
            if username in centroids:
                if acct_type not in type_embeddings:
                    type_embeddings[acct_type] = []
                type_embeddings[acct_type].append(centroids[username])

        type_centroids = {}
        for acct_type, vecs in type_embeddings.items():
            type_centroids[acct_type] = np.mean(vecs, axis=0)
        print(f"Type centroids: {list(type_centroids.keys())}")

        # Classify remaining accounts
        similarity_results = classify_remaining_by_similarity(
            accounts, centroids, type_centroids, classified
        )
        print(f"Similarity classified: {len(similarity_results)} accounts")

        # Merge all classifications
        all_classifications = {**classified, **similarity_results}
        results = build_output(accounts, all_classifications)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"accounts": results, "stats": {
                "total_accounts": len(accounts),
                "total_posts": len(posts),
                "types": ACCOUNT_TYPES,
                "llm_classified": len(classified),
                "similarity_classified": len(similarity_results),
            }}, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(results)} accounts → {output_path}")


if __name__ == "__main__":
    main()
