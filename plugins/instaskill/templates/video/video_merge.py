"""
Phase 5: Video Merge — Deterministic Trust Hierarchy

Merges Opus extraction + Gemini enrichment into final authoritative file.

Trust hierarchy:
  - Opus = ground truth. NEVER overridden.
  - Gemini = additive only. Appends missed items, never replaces.
  - This merge = deterministic script. No LLM, no interpretation.

Input: data/video_extracted.json + data/gemini_enrichments/enrichment_results.json
Output: data/video_final.json + data/convex_export/*.jsonl + QA report

Usage:
  python video_merge.py                    # Full merge + export
  python video_merge.py --dry              # Preview only
  python video_merge.py stats              # Show counts
"""

import json
import time
from pathlib import Path

# ============ CONFIGURATION ============
# Default paths — override with --data-dir for collection-scoped directories
# e.g., --data-dir data/food  →  data/food/video_extracted.json, etc.
DATA_DIR = Path("data")
EXTRACTED_PATH = DATA_DIR / "video_extracted.json"
ENRICHMENT_PATH = DATA_DIR / "gemini_enrichments" / "enrichment_results.json"
OUTPUT_PATH = DATA_DIR / "video_final.json"
EXPORT_DIR = DATA_DIR / "convex_export"
QA_DIR = DATA_DIR / "qa"
# =======================================


def load_json(path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def merge_arrays(opus_list, gemini_list, tag="video-only"):
    """Merge Gemini items into Opus list, deduplicating."""
    if not gemini_list:
        return opus_list

    existing = set()
    for item in opus_list:
        if isinstance(item, dict):
            existing.add(item.get("item", "").lower())
        else:
            existing.add(str(item).lower())

    added = []
    for item in gemini_list:
        text = item.get("item", item) if isinstance(item, dict) else str(item)
        if text.lower() not in existing:
            if isinstance(item, dict):
                item["source"] = tag
                added.append(item)
            else:
                added.append({"item": str(item), "source": tag})

    return opus_list + added


def merge_post(opus, gemini):
    """Merge a single post's Opus + Gemini data. Opus is ground truth."""
    if not gemini:
        return opus, []

    changes = []

    # Gemini missedIngredients → append to ingredients (if field exists)
    missed_ingredients = gemini.get("missedIngredients", [])
    if missed_ingredients and "ingredients" in opus:
        before = len(opus["ingredients"])
        opus["ingredients"] = merge_arrays(opus["ingredients"], missed_ingredients)
        after = len(opus["ingredients"])
        if after > before:
            changes.append(f"+{after - before} ingredients from Gemini")

    # Gemini missedTechniques → append to tips (NOT instructions)
    missed_techniques = gemini.get("missedTechniques", [])
    if missed_techniques:
        tips = opus.get("tips", [])
        for tech in missed_techniques:
            tip = f"[video technique] {tech}" if isinstance(tech, str) else str(tech)
            if tip not in tips:
                tips.append(tip)
                changes.append(f"+tip: {tip[:50]}")
        opus["tips"] = tips

    # Gemini corrections → store as informational, NEVER apply
    corrections = gemini.get("corrections", [])
    if corrections:
        opus["geminiCorrections"] = corrections
        changes.append(f"{len(corrections)} corrections noted (not applied)")

    # Gemini audio/motion insights → videoOnlyInsights
    audio = gemini.get("audioInsights", [])
    motion = gemini.get("motionInsights", [])
    existing_insights = opus.get("videoOnlyInsights", [])
    for insight in audio + motion:
        if isinstance(insight, str) and insight not in existing_insights:
            existing_insights.append(insight)
            changes.append(f"+insight: {insight[:50]}")
    opus["videoOnlyInsights"] = existing_insights

    # Store Gemini metadata
    opus["geminiAddedValue"] = gemini.get("overallAddedValue", "none")

    return opus, changes


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="merge", choices=["merge", "stats"])
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Base data directory (e.g., data/food for collection-scoped paths)")
    args = parser.parse_args()

    # Resolve collection-scoped paths
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    extracted_path = data_dir / "video_extracted.json"
    enrichment_path = data_dir / "gemini_enrichments" / "enrichment_results.json"
    output_path = data_dir / "video_final.json"
    export_dir = data_dir / "convex_export"
    qa_dir = data_dir / "qa"

    if args.command == "stats":
        extracted = load_json(extracted_path)
        enriched = load_json(enrichment_path)
        final = load_json(output_path) if output_path.exists() else []
        print(f"Extracted (Opus): {len(extracted)}")
        print(f"Enriched (Gemini): {len(enriched)}")
        print(f"Final (merged): {len(final)}")
        return

    dry_run = args.dry

    extracted = load_json(extracted_path)
    enriched = load_json(enrichment_path)

    print(f"Opus results: {len(extracted)}")
    print(f"Gemini enrichments: {len(enriched)}")

    # Build enrichment lookup
    enrichment_map = {e.get("postId", ""): e for e in enriched}

    # Merge
    merged = []
    changelog = []
    for opus in extracted:
        post_id = opus.get("postId", "")
        gemini = enrichment_map.get(post_id)
        result, changes = merge_post(opus.copy(), gemini)
        merged.append(result)

        if changes:
            changelog.append({
                "postId": post_id,
                "changes": changes,
                "geminiAddedValue": gemini.get("overallAddedValue", "none") if gemini else "none",
            })

    # Stats
    with_gemini = sum(1 for m in merged if m.get("geminiAddedValue", "none") != "none")
    print(f"\nMerged: {len(merged)} posts")
    print(f"With Gemini additions: {with_gemini}")
    print(f"Changelog entries: {len(changelog)}")

    if dry_run:
        print("\n[DRY RUN — no files written]")
        for entry in changelog[:10]:
            print(f"  {entry['postId']}: {', '.join(entry['changes'][:3])}")
        return

    # Save merged
    with open(output_path, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {output_path}")

    # QA report
    qa_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    qa_path = qa_dir / f"merge_changelog_{ts}.json"
    with open(qa_path, "w") as f:
        json.dump(changelog, f, ensure_ascii=False, indent=2)
    print(f"QA report → {qa_path}")

    # Summary
    summary_path = qa_dir / f"merge_summary_{ts}.txt"
    with open(summary_path, "w") as f:
        f.write(f"Video Merge Summary\n{'='*50}\n")
        f.write(f"Opus results: {len(extracted)}\n")
        f.write(f"Gemini enrichments: {len(enriched)}\n")
        f.write(f"Merged: {len(merged)}\n")
        f.write(f"With Gemini additions: {with_gemini}\n")
        f.write(f"Changelog entries: {len(changelog)}\n\n")
        for entry in changelog:
            f.write(f"{entry['postId']} [{entry['geminiAddedValue']}]:\n")
            for change in entry["changes"]:
                f.write(f"  - {change}\n")
            f.write("\n")
    print(f"Summary → {summary_path}")

    # Export JSONL
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / "videoAnalysis.jsonl"
    with open(export_path, "w") as f:
        for item in merged:
            # Serialize complex fields
            row = {}
            for k, v in item.items():
                if v is None:
                    continue
                if isinstance(v, (list, dict)):
                    row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    row[k] = v
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Exported → {export_path}")


if __name__ == "__main__":
    main()
