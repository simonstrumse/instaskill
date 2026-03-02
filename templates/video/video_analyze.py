"""
Phase 2-3: Video Analysis — Claude Subagent Batch Processing

Sends batches of key frames to Claude Opus/Sonnet subagents for structured extraction.
The extraction schema is customizable — replace the EXTRACTION_SCHEMA and SYSTEM_PROMPT
for your domain.

Input: data/video_manifest.json + frame images
Output: data/video_extracted.json

Usage:
  python video_analyze.py analyze --model opus --batch-size 6
  python video_analyze.py merge                                  # Merge batch results
  python video_analyze.py stats                                  # Show counts
"""

import base64
import json
import sys
import time
from pathlib import Path

# ============ CONFIGURATION ============
MANIFEST_PATH = Path("data/video_manifest.json")
OUTPUT_PATH = Path("data/video_extracted.json")
BATCH_DIR = Path("data/video_batches")

# Extraction schema — customize for your domain.
# This example extracts recipes. Replace fields for art analysis, tutorials, etc.
EXTRACTION_SCHEMA = {
    "postId": "string",
    "title": "string",
    "slug": "url-safe-string",
    "description": "1-2 sentence summary",
    "videoSummary": "literal description of what happens in the video",
    "videoOnlyInsights": ["things ONLY visible in video, not in text"],
    "confidence": "high|medium|low",
    # --- Domain-specific fields (recipe example) ---
    # "isRecipe": "boolean",
    # "ingredients": [{"amount": "", "item": "", "note": ""}],
    # "instructions": [{"step": 1, "text": ""}],
    # "tips": ["string"],
    # "cuisineTags": [], "dietaryTags": [],
}

SYSTEM_PROMPT = """You are analyzing Instagram video content through key frames.
For each post, examine all frames carefully and extract structured data.

Return your analysis as a JSON array with one object per post.
Be precise — only report what you can actually see in the frames.
If unsure, set confidence to "low"."""

DEFAULT_MODEL = "claude-opus-4-20250514"
DEFAULT_BATCH_SIZE = 6
# =======================================


def load_manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def image_to_base64(path):
    """Read an image file and return base64-encoded string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_batch_prompt(batch_items, posts_context=None):
    """Build the analysis prompt for a batch of videos."""
    schema_str = json.dumps(EXTRACTION_SCHEMA, indent=2)

    lines = [
        f"Analyze {len(batch_items)} video posts from their key frames.",
        f"\nExtraction schema (one object per post):\n```json\n{schema_str}\n```",
        "\nFor each post below, I'll show the key frames. Analyze all frames together.\n",
    ]

    for item in batch_items:
        post_id = item["postId"]
        lines.append(f"--- POST {post_id} ---")
        # Additional text context if available
        if posts_context and post_id in posts_context:
            ctx = posts_context[post_id]
            if ctx.get("text"):
                lines.append(f"Caption: {ctx['text'][:300]}")
            if ctx.get("final_explainer"):
                lines.append(f"Explainer: {ctx['final_explainer'][:300]}")
        lines.append(f"[{item['frameCount']} frames follow]")
        lines.append("")

    lines.append(f"\nRespond with a JSON array of {len(batch_items)} objects matching the schema above.")
    return "\n".join(lines)


def build_vision_messages(batch_items, text_prompt):
    """Build messages with image content for Claude vision API."""
    content = [{"type": "text", "text": text_prompt}]

    for item in batch_items:
        content.append({"type": "text", "text": f"\n--- Frames for {item['postId']} ---"})
        for frame_path in item.get("framePaths", []):
            if Path(frame_path).exists():
                b64 = image_to_base64(frame_path)
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64,
                    },
                })

    return [{"role": "user", "content": content}]


def analyze_batch(batch_items, client, model, posts_context=None):
    """Send a batch to Claude for analysis."""
    prompt = build_batch_prompt(batch_items, posts_context)
    messages = build_vision_messages(batch_items, prompt)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    text = response.content[0].text
    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\[.*\]', text, re.DOTALL)
        results = json.loads(match.group()) if match else []

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["analyze", "merge", "stats"])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.command == "stats":
        if OUTPUT_PATH.exists():
            with open(OUTPUT_PATH) as f:
                data = json.load(f)
            print(f"Extracted: {len(data)} posts")
        batch_files = list(BATCH_DIR.glob("batch_*.json")) if BATCH_DIR.exists() else []
        print(f"Batch files: {len(batch_files)}")
        return

    if args.command == "merge":
        all_results = {}
        for f in sorted(BATCH_DIR.glob("batch_*.json")):
            with open(f) as fh:
                batch = json.load(fh)
            for item in batch:
                pid = item.get("postId", "")
                if pid:
                    all_results[pid] = item  # Dedup by postId

        results = list(all_results.values())
        with open(OUTPUT_PATH, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Merged {len(results)} unique posts → {OUTPUT_PATH}")
        return

    # ============ ANALYZE ============
    from anthropic import Anthropic
    client = Anthropic()

    manifest = load_manifest()
    if args.limit:
        manifest = manifest[:args.limit]

    # Skip already-processed
    existing = set()
    if BATCH_DIR.exists():
        for f in BATCH_DIR.glob("batch_*.json"):
            with open(f) as fh:
                for item in json.load(fh):
                    existing.add(item.get("postId", ""))

    remaining = [m for m in manifest if m["postId"] not in existing]
    print(f"Total: {len(manifest)}, Already processed: {len(existing)}, Remaining: {len(remaining)}")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batch_idx = len(list(BATCH_DIR.glob("batch_*.json")))

    for i in range(0, len(remaining), args.batch_size):
        batch = remaining[i:i+args.batch_size]
        print(f"Batch {batch_idx}: {len(batch)} posts ({args.model})...", end=" ", flush=True)

        try:
            results = analyze_batch(batch, client, args.model)
            # Save batch
            batch_path = BATCH_DIR / f"batch_{batch_idx:04d}.json"
            with open(batch_path, "w") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"OK ({len(results)} results)")
            batch_idx += 1
        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(1)  # Rate limiting

    print(f"\nDone. Run 'python {sys.argv[0]} merge' to combine results.")


if __name__ == "__main__":
    main()
