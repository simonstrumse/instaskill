"""
Phase 0: Synthesis Runner

Calls Claude Haiku to synthesize caption + OCR + audio + vision analysis into one
searchable paragraph (final_explainer) per post. Safe to interrupt and resume.

Input: saved_posts.json (posts lacking final_explainer)
Output: saved_posts.json (updated in-place with final_explainer fields)

Customize: POSTS_PATH, MODEL, BATCH_SIZE at top of file.
"""

import json
import os
import sys
import time
import fcntl
import tempfile
from pathlib import Path

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 15          # Posts per API call
SAVE_EVERY = 20          # Save checkpoint every N posts
RATE_LIMIT_DELAY = 1.0   # Seconds between API calls
# =======================================


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

    # Caption
    text = post.get("text", "")
    if text:
        parts.append(f"Caption: {text[:500]}")

    # OCR
    et = post.get("extracted_text", {}) or {}
    for ocr in (et.get("ocr_texts", []) or []):
        if ocr:
            parts.append(f"On-screen text: {ocr[:300]}")

    # Audio
    for audio in (et.get("audio_transcripts", []) or []):
        if audio:
            parts.append(f"Audio: {audio[:500]}")

    # Vision analysis
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


def synthesize_batch(posts_batch, client):
    """Send a batch of posts to Claude Haiku for synthesis."""
    inputs = []
    for post in posts_batch:
        pid = post["id"]
        content = build_synthesis_input(post)
        inputs.append(f"[POST {pid}]\n{content}")

    prompt = (
        "For each Instagram post below, write a concise searchable paragraph (100-400 words) "
        "that synthesizes ALL information sources (caption, on-screen text, audio transcription, "
        "vision analysis) into one coherent description. Remove duplicates between sources. "
        "Preserve the original language where meaningful.\n\n"
        "Respond as JSON: [{\"post_id\": \"...\", \"explainer\": \"...\"}]\n\n"
        + "\n\n".join(inputs)
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    # Parse JSON from response
    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            results = json.loads(match.group())
        else:
            results = []

    return {r["post_id"]: r["explainer"] for r in results}


def main():
    if "--stats" in sys.argv:
        posts = load_posts()
        with_explainer = sum(1 for p in posts if p.get("final_explainer"))
        print(f"Total: {len(posts)}, With explainer: {with_explainer}, "
              f"Remaining: {len(posts) - with_explainer}")
        return

    from anthropic import Anthropic
    client = Anthropic()

    posts = load_posts()
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

        try:
            results = synthesize_batch(batch, client)
            for pid, explainer in results.items():
                if pid in post_lookup:
                    post_lookup[pid]["final_explainer"] = explainer
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


if __name__ == "__main__":
    main()
