"""
Step 5: Narrative Classification

Classifies posts into domain-specific narrative frames using Claude subagents.
Includes a discovery mode that samples posts to identify frames before classification.

Two phases:
  1. Discovery: Sample 200 posts → identify recurring frames
  2. Classification: Batch-classify all posts into discovered frames

Output: {OUTPUT_DIR}/{slug}_narratives.json

Customize: NARRATIVE_FRAMES in config.py (populated after discovery phase)
Dependencies: Claude subagents (free on Max plan)
"""

import json
from collections import Counter

from config import (
    COLLECTION_SLUG, COLLECTION_NAME, NARRATIVE_FRAMES,
    OUTPUT_DIR, OUTPUT_POSTS,
)

BATCH_SIZE = 100
CHECKPOINT_DIR = OUTPUT_DIR / "narrative_batches"


def load_posts():
    with open(OUTPUT_POSTS, "r", encoding="utf-8") as f:
        return json.load(f)


def build_discovery_prompt(sample_posts):
    """Build a prompt to discover narrative frames from a sample of posts."""
    lines = [
        f"Analyze these {len(sample_posts)} posts from an Instagram collection called \"{COLLECTION_NAME}\".",
        "Identify 5-8 recurring narrative frames — the dominant ways these posts frame their content.",
        "",
        "A 'frame' is not a topic but a perspective or rhetorical strategy. Examples:",
        "  - 'witness': first-person testimony or documentation",
        "  - 'solidarity': calls for collective action or empathy",
        "  - 'satire': humor used to critique or subvert",
        "  - 'tutorial': instructional or educational content",
        "",
        "Posts:\n",
    ]

    for i, post in enumerate(sample_posts):
        text = (post.get("final_explainer", "") or "")[:300]
        mood = post.get("vision_analysis", {}).get("mood", "")
        tone = post.get("vision_analysis", {}).get("tone", "")
        lines.append(f"[{i+1}] mood={mood}, tone={tone}")
        lines.append(f"    {text}")
        lines.append("")

    lines.append("Respond as JSON: {\"frames\": [{\"name\": \"snake_case\", \"description\": \"...\", \"count_estimate\": N}]}")
    return "\n".join(lines)


def build_classification_prompt(batch, frames):
    """Build a prompt to classify a batch of posts into the discovered frames."""
    frame_list = ", ".join(frames)
    lines = [
        f"Classify each post into exactly one narrative frame.",
        f"Available frames: {frame_list}",
        f"If none fit well, use 'other'.",
        "",
        "Posts:\n",
    ]

    for post in batch:
        pid = post["id"]
        text = (post.get("final_explainer", "") or "")[:400]
        mood = post.get("vision_analysis", {}).get("mood", "")
        lines.append(f"[{pid}] mood={mood}")
        lines.append(f"  {text}")
        lines.append("")

    lines.append("Respond as JSON array: [{\"post_id\": \"...\", \"frame\": \"...\", \"confidence\": 0.0-1.0}]")
    return "\n".join(lines)


def load_checkpoint():
    """Load previously classified results from checkpoint files."""
    results = {}
    if CHECKPOINT_DIR.exists():
        for f in sorted(CHECKPOINT_DIR.glob("batch_*.json")):
            with open(f) as fh:
                batch_results = json.load(fh)
            for item in batch_results:
                results[item["post_id"]] = item
    return results


def save_checkpoint(batch_idx, results):
    """Save batch results as checkpoint."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"batch_{batch_idx:04d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def main():
    posts = load_posts()
    print(f"Loaded {len(posts)} posts")

    if not NARRATIVE_FRAMES:
        # ============ DISCOVERY MODE ============
        print("\n--- DISCOVERY MODE ---")
        print("NARRATIVE_FRAMES is empty. Generating discovery prompt.")

        import random
        sample = random.sample(posts, min(200, len(posts)))

        prompt = build_discovery_prompt(sample)
        prompt_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_frame_discovery_prompt.txt"
        with open(prompt_path, "w") as f:
            f.write(prompt)
        print(f"\nDiscovery prompt saved → {prompt_path}")
        print(f"Feed this to a Claude Sonnet subagent.")
        print(f"Then update NARRATIVE_FRAMES in config.py and re-run.")
        return

    # ============ CLASSIFICATION MODE ============
    print(f"\nClassifying with frames: {NARRATIVE_FRAMES}")

    # Resume from checkpoint
    classified = load_checkpoint()
    remaining = [p for p in posts if p["id"] not in classified]
    print(f"Already classified: {len(classified)}, Remaining: {len(remaining)}")

    if not remaining:
        print("All posts classified.")
    else:
        # Build classification batches
        batches = [remaining[i:i+BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
        print(f"Batches to process: {len(batches)} (size {BATCH_SIZE})")

        for batch_idx, batch in enumerate(batches):
            prompt = build_classification_prompt(batch, NARRATIVE_FRAMES)
            prompt_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_narrative_batch_{batch_idx:04d}.txt"
            with open(prompt_path, "w") as f:
                f.write(prompt)
            print(f"  Batch {batch_idx}: {len(batch)} posts → {prompt_path}")

        print(f"\nFeed each batch prompt to a Claude Haiku subagent.")
        print(f"Save results as JSON in {CHECKPOINT_DIR}/batch_NNNN.json")
        print(f"Then re-run to merge results.")
        return

    # Merge all results
    all_results = []
    frame_counts = Counter()

    for post in posts:
        pid = post["id"]
        cls = classified.get(pid, {"frame": "other", "confidence": 0.0})
        all_results.append({
            "post_id": pid,
            "frame": cls.get("frame", "other"),
            "confidence": cls.get("confidence", 0.0),
        })
        frame_counts[cls.get("frame", "other")] += 1

    # Stats
    print(f"\nFrame distribution:")
    for frame, count in frame_counts.most_common():
        pct = count / len(posts) * 100
        print(f"  {frame:30s} {count:5d} ({pct:.1f}%)")

    # Save
    output_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_narratives.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "classifications": all_results,
            "frames": NARRATIVE_FRAMES,
            "distribution": dict(frame_counts),
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    main()
