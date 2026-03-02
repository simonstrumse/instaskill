"""
Phase 0b: Synthesis Runner

Synthesizes caption + OCR + audio + vision analysis into one searchable paragraph
(final_explainer) per post. Safe to interrupt and resume.

TWO MODES:
  --mode subagent  (DEFAULT) Generates prompt files for Claude subagents (FREE on Max plan).
                   The agent reads the prompts and feeds them to subagents.
  --mode api       Uses direct Anthropic API calls (PAID, requires ANTHROPIC_API_KEY).
                   Faster batch processing, but costs money per token.

Input: saved_posts.json (posts lacking final_explainer)
Output:
  subagent mode: data/synthesis_prompts/ directory with batch prompt files
  api mode:      saved_posts.json (updated in-place with final_explainer fields)

Customize: POSTS_PATH, MODEL, BATCH_SIZE at top of file.
"""

import json
import sys
import time
from pathlib import Path

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 15          # Posts per batch/API call
SAVE_EVERY = 20          # Save checkpoint every N posts (api mode)
RATE_LIMIT_DELAY = 1.0   # Seconds between API calls (api mode)
PROMPTS_DIR = Path("data/synthesis_prompts")  # For subagent mode
# =======================================


SYNTHESIS_INSTRUCTION = (
    "For each Instagram post below, write a concise searchable paragraph (100-400 words) "
    "that synthesizes ALL information sources (caption, on-screen text, audio transcription, "
    "vision analysis) into one coherent description. Remove duplicates between sources. "
    "Preserve the original language where meaningful.\n\n"
    "Respond as JSON: [{\"post_id\": \"...\", \"explainer\": \"...\"}]"
)


def load_posts():
    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posts_atomic(posts):
    """Atomic write: write to tmp, then rename."""
    tmp = POSTS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    tmp.rename(POSTS_PATH)


def build_synthesis_input(post):
    """Build compact input from all available text sources."""
    parts = []

    text = post.get("text", "")
    if text:
        parts.append(f"Caption: {text[:500]}")

    et = post.get("extracted_text", {}) or {}
    for ocr in (et.get("ocr_texts", []) or []):
        if ocr:
            parts.append(f"On-screen text: {ocr[:300]}")
    for audio in (et.get("audio_transcripts", []) or []):
        if audio:
            parts.append(f"Audio: {audio[:500]}")

    va = post.get("vision_analysis", {}) or {}
    if va:
        va_parts = []
        for field in ["mood", "tone", "content_style", "language"]:
            val = va.get(field)
            if val:
                va_parts.append(f"{field}={val}")
        cats = va.get("categories", [])
        if cats:
            va_parts.append(f"categories={','.join(cats[:5])}")
        tags = va.get("tags", [])
        if tags:
            va_parts.append(f"tags={','.join(tags[:10])}")
        if va_parts:
            parts.append(f"Vision: {'; '.join(va_parts)}")

    return "\n".join(parts)


def generate_subagent_prompts(posts):
    """Generate prompt files that an agent can feed to Claude subagents (FREE)."""
    remaining = [p for p in posts if not p.get("final_explainer")]
    print(f"Total: {len(posts)}, Remaining: {len(remaining)}")

    if not remaining:
        print("All posts have final_explainer.")
        return

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    batch_num = 0

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i+BATCH_SIZE]
        inputs = []
        for post in batch:
            pid = post["id"]
            content = build_synthesis_input(post)
            inputs.append(f"[POST {pid}]\n{content}")

        prompt = SYNTHESIS_INSTRUCTION + "\n\n" + "\n\n".join(inputs)
        prompt_path = PROMPTS_DIR / f"batch_{batch_num:04d}.txt"
        with open(prompt_path, "w") as f:
            f.write(prompt)
        batch_num += 1

    print(f"\nGenerated {batch_num} prompt files in {PROMPTS_DIR}/")
    print(f"Feed each file to a Claude Haiku subagent, then merge results back into saved_posts.json")
    print(f"\nExpected response format per batch: JSON array of {{\"post_id\": \"...\", \"explainer\": \"...\"}}")


def run_api_mode(posts):
    """Run synthesis via direct Anthropic API calls (PAID)."""
    from anthropic import Anthropic
    client = Anthropic()

    remaining = [p for p in posts if not p.get("final_explainer")]
    print(f"Total: {len(posts)}, Remaining: {len(remaining)}")

    if not remaining:
        print("All posts have final_explainer.")
        return

    post_lookup = {p["id"]: p for p in posts}
    processed = 0

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i+BATCH_SIZE]
        print(f"Batch {i//BATCH_SIZE + 1}: {len(batch)} posts...", end=" ", flush=True)

        inputs = []
        for post in batch:
            pid = post["id"]
            content = build_synthesis_input(post)
            inputs.append(f"[POST {pid}]\n{content}")

        prompt = SYNTHESIS_INSTRUCTION + "\n\n" + "\n\n".join(inputs)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            try:
                results = json.loads(text)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\[.*\]', text, re.DOTALL)
                results = json.loads(match.group()) if match else []

            for r in results:
                pid = r.get("post_id", "")
                if pid in post_lookup:
                    post_lookup[pid]["final_explainer"] = r["explainer"]
                    processed += 1
            print(f"OK ({len(results)} synthesized)")
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        if processed % SAVE_EVERY < BATCH_SIZE:
            save_posts_atomic(posts)
            print(f"  [checkpoint: {processed} total]")

        time.sleep(RATE_LIMIT_DELAY)

    save_posts_atomic(posts)
    print(f"\nDone. Synthesized {processed} posts.")


def main():
    if "--stats" in sys.argv:
        posts = load_posts()
        with_explainer = sum(1 for p in posts if p.get("final_explainer"))
        print(f"Total: {len(posts)}, With explainer: {with_explainer}, "
              f"Remaining: {len(posts) - with_explainer}")
        return

    # Default to subagent mode (free)
    mode = "subagent"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]

    posts = load_posts()

    if mode == "api":
        print("Running in API mode (PAID — requires ANTHROPIC_API_KEY)")
        run_api_mode(posts)
    else:
        print("Running in subagent mode (FREE on Max plan)")
        generate_subagent_prompts(posts)


if __name__ == "__main__":
    main()
