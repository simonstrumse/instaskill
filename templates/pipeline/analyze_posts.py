"""
Phase 9a: Analysis Report

Generates a comprehensive statistics report from the processed posts.
Loads all data once and computes metrics in memory.

Input:  data/instagram/saved_posts.json (with vision_analysis, extracted_text, final_explainer)
Output: data/analysis_report.json

Customize: INPUT_PATH, OUTPUT_PATH
"""

import json
import os
from collections import Counter
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────
INPUT_PATH = "data/instagram/saved_posts.json"
OUTPUT_PATH = "data/analysis_report.json"
# ───────────────────────────────────────────────────────────────────────────


def safe_str(v):
    return str(v).strip() if v else ""


def safe_list(v):
    return v if isinstance(v, list) else []


def top_n(counter, n=20):
    return [{"value": k, "count": v} for k, v in counter.most_common(n)]


def pct(num, total):
    return round(100.0 * num / total, 2) if total else 0.0


def main():
    print("Loading data...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)

    total = len(posts)
    print(f"Loaded {total} posts.")

    # ── Counters ──────────────────────────────────────────────────────
    media_types = Counter()
    collections = Counter()
    authors = Counter()
    moods = Counter()
    tones = Counter()
    categories = Counter()
    tags = Counter()
    humor_types = Counter()
    languages = Counter()
    content_styles = Counter()
    monthly = Counter()

    has_vision = 0
    has_text = 0
    has_explainer = 0
    has_audio = 0
    has_ocr = 0

    # ── Scan ──────────────────────────────────────────────────────────
    for post in posts:
        # Author
        author = post.get("author", {})
        username = author.get("username", "unknown")
        authors[username] += 1

        # Collections
        for c in safe_list(post.get("collections", [])):
            collections[c] += 1

        # Media type
        media = safe_list(post.get("media", []))
        for m in media:
            media_types[m.get("type", "unknown")] += 1

        # Dates
        ts = post.get("created_at", "")
        if ts and len(ts) >= 7:
            monthly[ts[:7]] += 1

        # Vision analysis
        va = post.get("vision_analysis", {})
        if va:
            has_vision += 1
            moods[safe_str(va.get("mood"))] += 1
            tones[safe_str(va.get("tone"))] += 1
            content_styles[safe_str(va.get("content_style"))] += 1
            languages[safe_str(va.get("language"))] += 1

            # humor_type can be string or list
            humor = va.get("humor_type", "none") or "none"
            if isinstance(humor, list):
                humor = humor[0] if humor else "none"
            humor_types[str(humor)] += 1

            for cat in safe_list(va.get("categories", [])):
                categories[cat] += 1
            for tag in safe_list(va.get("tags", [])):
                tags[tag] += 1

        # Extracted text
        et = post.get("extracted_text", {})
        if et:
            has_text += 1
            if et.get("audio_transcripts"):
                has_audio += 1
            if et.get("ocr_texts"):
                has_ocr += 1

        # Final explainer
        if post.get("final_explainer"):
            has_explainer += 1

    # ── Report ────────────────────────────────────────────────────────
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_posts": total,
        "coverage": {
            "vision_analysis": has_vision,
            "extracted_text": has_text,
            "audio_transcripts": has_audio,
            "ocr_texts": has_ocr,
            "final_explainer": has_explainer,
            "vision_pct": pct(has_vision, total),
            "explainer_pct": pct(has_explainer, total),
        },
        "top_authors": top_n(authors),
        "collections": top_n(collections, 50),
        "media_types": top_n(media_types),
        "monthly_volume": dict(sorted(monthly.items())),
        "unique_authors": len(authors),
        "unique_collections": len(collections),
        "vision": {
            "top_moods": top_n(moods),
            "top_tones": top_n(tones),
            "top_categories": top_n(categories, 30),
            "top_tags": top_n(tags, 50),
            "top_humor_types": top_n(humor_types),
            "top_content_styles": top_n(content_styles),
            "languages": top_n(languages),
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReport saved to {OUTPUT_PATH}")
    print(f"  Posts: {total}")
    print(f"  Authors: {len(authors)}")
    print(f"  Collections: {len(collections)}")
    print(f"  Vision: {has_vision} ({pct(has_vision, total)}%)")
    print(f"  Explainer: {has_explainer} ({pct(has_explainer, total)}%)")


if __name__ == "__main__":
    main()
