"""
Phase 4: Gemini Enrichment

Sends full videos to Gemini 2.0 Flash for comparison against Opus results.
Gemini watches the complete video (not just key frames) and reports what Opus missed.

IMPORTANT: Gemini output is NEVER treated as ground truth. Only additive.

Input: data/video_extracted.json + video files
Output: data/gemini_enrichments/enrichment_results.json

Requires: GOOGLE_API_KEY in environment or .env file
"""

import json
import os
import sys
import time
from pathlib import Path

# ============ CONFIGURATION ============
# Default paths — override with --data-dir for collection-scoped directories
# e.g., --data-dir data/food  →  data/food/videos, data/food/video_extracted.json, etc.
DATA_DIR = Path("data")
VIDEO_DIR = DATA_DIR / "videos"
EXTRACTED_PATH = DATA_DIR / "video_extracted.json"
OUTPUT_DIR = DATA_DIR / "gemini_enrichments"
OUTPUT_PATH = OUTPUT_DIR / "enrichment_results.json"
DEFAULT_DELAY = 5  # Seconds between API calls
# =======================================

ENRICHMENT_PROMPT = """I've already analyzed this video using key frames. Here's what I found:
{existing_analysis}

Now watch the FULL video and tell me what I missed. Report ONLY genuinely new information:

1. missedIngredients: Items visible in video but not in my analysis
2. missedTechniques: Cooking/preparation methods I didn't catch
3. missedOnScreenText: Text overlays, captions, labels I missed
4. corrections: Factual errors in my analysis (be specific)
5. audioInsights: Things said in narration/voiceover not captured
6. motionInsights: Important movements, gestures, timing cues

Respond as JSON:
{{
  "postId": "{post_id}",
  "missedIngredients": [],
  "missedTechniques": [],
  "missedOnScreenText": [],
  "corrections": [],
  "audioInsights": [],
  "motionInsights": [],
  "overallAddedValue": "high|medium|low|none"
}}

If my analysis was comprehensive and you found nothing new, set overallAddedValue to "none"
and leave all arrays empty. Do NOT hallucinate findings."""


def find_video(post_id, video_dir):
    """Find video file for a post ID."""
    for ext in [".mp4", ".mov", ".avi", ".webm"]:
        path = video_dir / f"{post_id}{ext}"
        if path.exists():
            return path
    return None


def enrich_with_gemini(video_path, existing, post_id, model):
    """Send full video to Gemini for enrichment."""
    import google.generativeai as genai

    # Upload video
    video_file = genai.upload_file(str(video_path))

    # Wait for processing
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name != "ACTIVE":
        return None

    # Build prompt with existing analysis
    analysis_summary = json.dumps(existing, indent=2, ensure_ascii=False)[:3000]
    prompt = ENRICHMENT_PROMPT.format(
        existing_analysis=analysis_summary,
        post_id=post_id,
    )

    response = model.generate_content([video_file, prompt])
    text = response.text

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        result = json.loads(match.group()) if match else None

    # Clean up uploaded file
    try:
        genai.delete_file(video_file.name)
    except Exception:
        pass

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Base data directory (e.g., data/food for collection-scoped paths)")
    parser.add_argument("--video-dir", type=str, default=None)
    args = parser.parse_args()

    # Resolve collection-scoped paths
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    video_dir = Path(args.video_dir) if args.video_dir else data_dir / "videos"
    extracted_path = data_dir / "video_extracted.json"
    output_dir = data_dir / "gemini_enrichments"
    output_path = output_dir / "enrichment_results.json"

    import google.generativeai as genai

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        # Try .env file
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GOOGLE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"')

    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set. Set in environment or .env file.")
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    with open(extracted_path) as f:
        extracted = json.load(f)

    # Load existing enrichments
    existing_results = {}
    if output_path.exists():
        with open(output_path) as f:
            for item in json.load(f):
                existing_results[item.get("postId", "")] = item

    remaining = [e for e in extracted if e.get("postId") not in existing_results]
    if args.limit:
        remaining = remaining[:args.limit]

    print(f"Extracted: {len(extracted)}, Already enriched: {len(existing_results)}, "
          f"Remaining: {len(remaining)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    new_results = []

    for i, item in enumerate(remaining):
        post_id = item.get("postId", "")
        video_path = find_video(post_id, video_dir)

        if not video_path:
            print(f"  [{i+1}] {post_id}: no video file, skipping")
            continue

        print(f"  [{i+1}/{len(remaining)}] {post_id}...", end=" ", flush=True)

        try:
            result = enrich_with_gemini(video_path, item, post_id, model)
            if result:
                new_results.append(result)
                added = result.get("overallAddedValue", "none")
                print(f"OK (added value: {added})")
            else:
                print("no result")
        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(args.delay)

    # Merge and save
    all_results = list(existing_results.values()) + new_results
    with open(output_path, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(all_results)} enrichments → {output_path}")

    # Stats
    added_values = [r.get("overallAddedValue", "none") for r in all_results]
    from collections import Counter
    dist = Counter(added_values)
    print(f"Added value: {dict(dist)}")


if __name__ == "__main__":
    main()
