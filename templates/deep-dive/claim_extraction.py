"""
Step 6: Claim Extraction

Extracts factual claims from post explainers with check-worthiness scoring.
Uses Claude Haiku subagents for batch extraction.

Output: {OUTPUT_DIR}/{slug}_claims.json

Customize: CLAIM_CATEGORIES in config.py
"""

import json
from collections import Counter

from config import (
    COLLECTION_SLUG, COLLECTION_NAME, CLAIM_CATEGORIES,
    OUTPUT_DIR, OUTPUT_POSTS,
)

BATCH_SIZE = 100
CHECKPOINT_DIR = OUTPUT_DIR / "claim_batches"


def load_posts():
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        return json.load(f)


def build_extraction_prompt(batch, categories):
    """Build a prompt for Claude Haiku to extract claims from a batch of posts."""
    cat_list = ", ".join(categories) if categories else "general"
    lines = [
        f"Extract factual claims from these posts in the \"{COLLECTION_NAME}\" collection.",
        f"Categories: {cat_list}",
        "",
        "For each claim, provide:",
        "  - claimText: the specific factual assertion",
        "  - category: one of the categories above",
        "  - checkWorthiness: 1-5 (5 = highly verifiable and impactful)",
        "  - postId: source post ID",
        "",
        "Only extract concrete factual claims, not opinions or emotions.",
        "Skip posts with no factual claims.",
        "",
        "Posts:\n",
    ]

    for post in batch:
        pid = post["id"]
        text = (post.get("final_explainer", "") or "")[:500]
        date = post.get("day", "")
        author = post.get("author", {}).get("username", "")
        lines.append(f"[{pid}] @{author} ({date})")
        lines.append(f"  {text}")
        lines.append("")

    lines.append("Respond as JSON array: [{\"claimText\": \"...\", \"category\": \"...\", \"checkWorthiness\": N, \"postId\": \"...\"}]")
    lines.append("Return empty array [] if no claims found.")
    return "\n".join(lines)


def load_checkpoint():
    """Load previously extracted claims from checkpoint files."""
    claims = []
    if CHECKPOINT_DIR.exists():
        for f in sorted(CHECKPOINT_DIR.glob("batch_*.json")):
            with open(f) as fh:
                batch_claims = json.load(fh)
            claims.extend(batch_claims)
    return claims


def main():
    posts = load_posts()
    print(f"Loaded {len(posts)} posts")

    if not CLAIM_CATEGORIES:
        print("\nWARNING: CLAIM_CATEGORIES is empty in config.py.")
        print("The agent will extract general claims without category filtering.")
        print("For better results, define domain-specific categories first.\n")

    # Check for existing claims
    existing_claims = load_checkpoint()
    classified_post_ids = set(c.get("postId") for c in existing_claims)
    remaining = [p for p in posts if p["id"] not in classified_post_ids]

    print(f"Existing claims: {len(existing_claims)} from {len(classified_post_ids)} posts")
    print(f"Remaining posts: {len(remaining)}")

    if not remaining:
        print("All posts processed.")
    else:
        # Generate batch prompts
        batches = [remaining[i:i+BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
        print(f"\nBatches to process: {len(batches)} (size {BATCH_SIZE})")

        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        for batch_idx, batch in enumerate(batches):
            prompt = build_extraction_prompt(batch, CLAIM_CATEGORIES)
            prompt_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_claim_batch_{batch_idx:04d}.txt"
            with open(prompt_path, "w") as f:
                f.write(prompt)
            print(f"  Batch {batch_idx}: {len(batch)} posts → {prompt_path}")

        print(f"\nFeed each batch prompt to a Claude Haiku subagent.")
        print(f"Save results as JSON in {CHECKPOINT_DIR}/batch_NNNN.json")
        print(f"Then re-run to merge results.")
        return

    # Merge all claims
    all_claims = existing_claims

    # Add date from post lookup
    post_lookup = {p["id"]: p for p in posts}
    for claim in all_claims:
        pid = claim.get("postId", "")
        post = post_lookup.get(pid, {})
        claim["date"] = post.get("day", "")
        claim["source"] = post.get("author", {}).get("username", "")

    # Stats
    cat_counts = Counter(c.get("category", "unknown") for c in all_claims)
    worthiness = [c.get("checkWorthiness", 0) for c in all_claims]

    print(f"\nTotal claims: {len(all_claims)}")
    print(f"Average check-worthiness: {sum(worthiness)/len(worthiness):.1f}" if worthiness else "")
    print(f"\nCategory distribution:")
    for cat, count in cat_counts.most_common():
        print(f"  {cat:30s} {count:5d}")

    # Save
    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_claims.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "claims": all_claims,
            "categories": CLAIM_CATEGORIES,
            "stats": {
                "total_claims": len(all_claims),
                "category_distribution": dict(cat_counts),
                "avg_check_worthiness": round(sum(worthiness)/len(worthiness), 2) if worthiness else 0,
            },
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    main()
