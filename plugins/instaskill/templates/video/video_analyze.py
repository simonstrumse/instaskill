"""
Phase 2-3: Video Analysis — Claude Vision Batch Processing

Sends batches of key frames to Claude Opus/Sonnet for structured extraction.
The extraction schema is customizable — replace the EXTRACTION_SCHEMA and SYSTEM_PROMPT
for your domain.

TWO MODES:
  --mode subagent  (DEFAULT) Generates prompt files with base64 images for Claude subagents
                   (FREE on Max plan). The agent reads each file and feeds it to a subagent.
  --mode api       Uses direct Anthropic API calls (PAID, requires ANTHROPIC_API_KEY).
                   Faster batch processing, but costs money per token.

Input: data/video_manifest.json + frame images
Output: data/video_extracted.json

Usage:
  python video_analyze.py analyze                            # Subagent mode (free)
  python video_analyze.py analyze --mode api --model opus    # API mode (paid)
  python video_analyze.py merge                              # Merge batch results
  python video_analyze.py stats                              # Show counts
"""

import base64
import json
import time
from pathlib import Path

# ============ CONFIGURATION ============
# Default paths — override with --data-dir for collection-scoped directories
# e.g., --data-dir data/food  →  data/food/video_manifest.json, etc.
DATA_DIR = Path("data")
MANIFEST_PATH = DATA_DIR / "video_manifest.json"
OUTPUT_PATH = DATA_DIR / "video_extracted.json"
BATCH_DIR = DATA_DIR / "video_batches"
PROMPTS_DIR = DATA_DIR / "video_prompts"  # For subagent mode

# Extraction schema — customize for your domain.
# This example extracts general video content. Uncomment domain-specific fields as needed.
EXTRACTION_SCHEMA = {
    "postId": "string",
    "title": "string",
    "slug": "url-safe-string",
    "description": "1-2 sentence summary",
    "videoSummary": "literal description of what happens in the video",
    "videoOnlyInsights": ["things ONLY visible in video, not in text"],
    "confidence": "high|medium|low",
    # --- Recipe extraction ---
    # "isRecipe": "boolean",
    # "ingredients": [{"amount": "", "item": "", "note": ""}],
    # "instructions": [{"step": 1, "text": ""}],
    # "tips": ["string"],
    # "cuisineTags": [], "dietaryTags": [],
    # --- Tutorial extraction ---
    # "tool": "string", "prerequisites": ["string"],
    # "steps": [{"step": 1, "text": "", "duration": ""}],
    # "difficulty": "beginner|intermediate|advanced",
    # --- Exercise extraction ---
    # "exercise": "string", "muscleGroup": "string",
    # "sets": "number", "reps": "string", "equipment": ["string"],
}

SYSTEM_PROMPT = """You are analyzing Instagram video content through key frames.
For each post, examine all frames carefully and extract structured data.

Return your analysis as a JSON array with one object per post.
Be precise — only report what you can actually see in the frames.
If unsure, set confidence to "low"."""

DEFAULT_MODEL = "claude-opus-4-20250514"
DEFAULT_BATCH_SIZE = 6
# =======================================


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


def get_processed(batch_dir):
    """Scan batch result files to find already-processed post IDs."""
    existing = set()
    batch_files = []
    if batch_dir.exists():
        batch_files = sorted(batch_dir.glob("batch_*.json"))
        for f in batch_files:
            with open(f) as fh:
                for item in json.load(fh):
                    existing.add(item.get("postId", ""))
    return existing, batch_files


def generate_subagent_prompts(manifest, batch_size, prompts_dir, batch_dir):
    """Generate prompt files that an agent can feed to Claude subagents (FREE)."""
    prompts_dir.mkdir(parents=True, exist_ok=True)

    existing, _ = get_processed(batch_dir)
    remaining = [m for m in manifest if m["postId"] not in existing]
    print(f"Total: {len(manifest)}, Already processed: {len(existing)}, Remaining: {len(remaining)}")

    if not remaining:
        print("All videos already processed.")
        return

    batch_num = 0
    for i in range(0, len(remaining), batch_size):
        batch = remaining[i:i+batch_size]
        prompt = build_batch_prompt(batch)

        # Write prompt text
        prompt_path = prompts_dir / f"batch_{batch_num:04d}.txt"
        with open(prompt_path, "w") as f:
            f.write(f"SYSTEM: {SYSTEM_PROMPT}\n\n{prompt}")

        # Write frame paths for the agent to include as images
        frames_path = prompts_dir / f"batch_{batch_num:04d}_frames.json"
        frame_data = []
        for item in batch:
            frame_data.append({
                "postId": item["postId"],
                "framePaths": item.get("framePaths", []),
            })
        with open(frames_path, "w") as f:
            json.dump(frame_data, f, indent=2)

        batch_num += 1

    print(f"\nGenerated {batch_num} prompt files in {prompts_dir}/")
    print(f"For each batch, feed the prompt + frame images to a Claude Opus subagent.")
    print(f"Save results as batch_NNNN.json in {batch_dir}/, then run 'merge' to combine.")


def run_api_mode(manifest, model, batch_size, batch_dir):
    """Run analysis via direct Anthropic API calls (PAID)."""
    from anthropic import Anthropic
    client = Anthropic()

    existing, batch_files = get_processed(batch_dir)
    remaining = [m for m in manifest if m["postId"] not in existing]
    print(f"Total: {len(manifest)}, Already processed: {len(existing)}, Remaining: {len(remaining)}")

    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_idx = len(batch_files)

    for i in range(0, len(remaining), batch_size):
        batch = remaining[i:i+batch_size]
        print(f"Batch {batch_idx}: {len(batch)} posts ({model})...", end=" ", flush=True)

        prompt = build_batch_prompt(batch)
        messages = build_vision_messages(batch, prompt)

        try:
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

            batch_path = batch_dir / f"batch_{batch_idx:04d}.json"
            with open(batch_path, "w") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"OK ({len(results)} results)")
            batch_idx += 1
        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(1)

    print(f"\nDone. Run 'merge' to combine results.")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["analyze", "merge", "stats"])
    parser.add_argument("--mode", default="subagent", choices=["subagent", "api"],
                        help="subagent (free on Max) or api (paid, requires ANTHROPIC_API_KEY)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Base data directory (e.g., data/food for collection-scoped paths)")
    args = parser.parse_args()

    # Resolve collection-scoped paths
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    manifest_path = data_dir / "video_manifest.json"
    output_path = data_dir / "video_extracted.json"
    batch_dir = data_dir / "video_batches"
    prompts_dir = data_dir / "video_prompts"

    if args.command == "stats":
        if output_path.exists():
            with open(output_path) as f:
                data = json.load(f)
            print(f"Extracted: {len(data)} posts")
        batch_files = list(batch_dir.glob("batch_*.json")) if batch_dir.exists() else []
        print(f"Batch files: {len(batch_files)}")
        prompt_files = list(prompts_dir.glob("batch_*.txt")) if prompts_dir.exists() else []
        print(f"Prompt files: {len(prompt_files)}")
        return

    if args.command == "merge":
        all_results = {}
        for f in sorted(batch_dir.glob("batch_*.json")):
            with open(f) as fh:
                batch_data = json.load(fh)
            for item in batch_data:
                pid = item.get("postId", "")
                if pid:
                    all_results[pid] = item
        results = list(all_results.values())
        with open(output_path, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Merged {len(results)} unique posts → {output_path}")
        return

    # ============ ANALYZE ============
    with open(manifest_path) as f:
        manifest = json.load(f)
    if args.limit:
        manifest = manifest[:args.limit]

    if args.mode == "api":
        print(f"Running in API mode (PAID — requires ANTHROPIC_API_KEY, model: {args.model})")
        run_api_mode(manifest, args.model, args.batch_size, batch_dir)
    else:
        print("Running in subagent mode (FREE on Max plan)")
        generate_subagent_prompts(manifest, args.batch_size, prompts_dir, batch_dir)


if __name__ == "__main__":
    main()
