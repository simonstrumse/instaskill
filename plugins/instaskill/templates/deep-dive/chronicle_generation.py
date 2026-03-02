"""
Step 8: Chronicle Generation

Uses Claude subagents to write editorial prose for the chronicle:
  - Header/lede: what is this archive? (~200 words)
  - Chapter introductions: what happened in this period? (~300-400 words each)
  - Epilogue: what does this collection tell us? (~200 words)

Output: {OUTPUT_DIR}/{slug}_chronicle_content.json
Export: {CONVEX_EXPORT_DIR}/{prefix}ChronicleContent.jsonl

The prompts are designed to produce documentary, measured prose. The agent feeds
these prompts to Claude subagents and collects the results.
"""

import json

from config import (
    COLLECTION_SLUG, COLLECTION_NAME, COLLECTION_PREFIX,
    OUTPUT_DIR, CONVEX_EXPORT_DIR,
)


def load_timeline():
    path = OUTPUT_DIR / f"{COLLECTION_SLUG}_timeline.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_lede_prompt(timeline):
    """Build the prompt for the chronicle header/lede."""
    stats = timeline.get("stats", {})
    total_posts = stats.get("total_posts", 0)
    total_events = stats.get("total_events", 0)
    chapters = timeline.get("chapters", [])
    ch_count = len(chapters)

    date_range = ""
    if chapters:
        date_range = f"{chapters[0]['startDate']} to {chapters[-1]['endDate']}"

    return f"""Write the opening lede for a data journalism feature story about an Instagram
saved-posts archive from the "{COLLECTION_NAME}" collection.

Key facts:
- {total_posts:,} posts saved between {date_range}
- {total_events} detected statistical events (spikes in saving activity)
- {ch_count} narrative chapters
- The archive is one person's curated information ecosystem, not objective reality

Tone: Documentary. Measured. The opening should make clear this is an investigation of
what one person's digital behavior reveals. ~200 words.
Do not use a title or heading. Just the prose paragraphs."""


def build_chapter_prompt(chapter, timeline):
    """Build the prompt for a chapter introduction."""
    frames = chapter.get("frameDistribution", {})
    top_frames = sorted(frames.items(), key=lambda x: -x[1])[:5]
    emotions = chapter.get("emotionSignature", {})
    top_emotions = sorted(emotions.items(), key=lambda x: -x[1])[:3]
    entities = chapter.get("topEntities", [])
    top_entity_names = [e["name"] if isinstance(e, dict) else str(e) for e in entities[:8]]

    context_parts = [
        f"Chapter: \"{chapter['title']}\"",
        f"Date range: {chapter['startDate']} to {chapter['endDate']}",
        f"Posts: {chapter['postCount']:,}, Events: {chapter['eventCount']}",
        f"Dominant frames: {', '.join(f'{f} ({c})' for f, c in top_frames)}",
        f"Emotional signature: {', '.join(f'{e} ({s:.0%})' for e, s in top_emotions)}",
        f"Key entities: {', '.join(top_entity_names)}",
    ]
    if chapter.get("subtitle"):
        context_parts.insert(1, f"Subtitle: {chapter['subtitle']}")
    if chapter.get("description"):
        context_parts.insert(2, f"Description: {chapter['description']}")

    context = "\n".join(context_parts)

    return f"""Write a chapter introduction for a data journalism feature about an Instagram
saved-posts archive from the "{COLLECTION_NAME}" collection.

{context}

Write 2-4 paragraphs (~300-400 words). Set the scene for this chapter's time period.
What was happening? What shifted in the archive? What does the data reveal?

Tone: Documentary, measured, precise. Reference specific numbers and patterns.
Do not use a title or heading. Just the prose paragraphs."""


def build_epilogue_prompt(timeline):
    """Build the prompt for the epilogue."""
    stats = timeline.get("stats", {})
    total_posts = stats.get("total_posts", 0)
    ch_count = stats.get("chapter_count", 0)

    return f"""Write a closing epilogue for a data journalism feature about an Instagram
saved-posts archive from the "{COLLECTION_NAME}" collection.

The reader has scrolled through {total_posts:,} posts across {ch_count} chapters.
The archive is biased, incomplete, shaped by algorithms and personal psychology
— and yet it documents something real.

Write a closing reflection (~200 words). What does this archive ultimately reveal?
End with something that lingers.

Tone: Quiet, reflective, documentary. No calls to action.
Do not use a title or heading. Just the prose paragraphs."""


def main():
    timeline = load_timeline()
    chapters = timeline.get("chapters", [])

    print(f"Generating chronicle prose for {COLLECTION_NAME}")
    print(f"  {len(chapters)} chapters")

    # Build all prompts
    prompts = []

    # 1. Lede
    prompts.append({
        "contentId": "header",
        "contentType": "header",
        "sortOrder": 0,
        "prompt": build_lede_prompt(timeline),
    })

    # 2. Chapter intros
    for i, ch in enumerate(chapters):
        prompts.append({
            "contentId": f"chapter_{ch['chapterId']}",
            "contentType": "chapter_intro",
            "chapterId": ch["chapterId"],
            "sortOrder": i + 1,
            "prompt": build_chapter_prompt(ch, timeline),
        })

    # 3. Epilogue
    prompts.append({
        "contentId": "epilogue",
        "contentType": "epilogue",
        "sortOrder": 99,
        "prompt": build_epilogue_prompt(timeline),
    })

    # Save prompts for agent to feed to subagents
    prompts_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_chronicle_prompts.json"
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(prompts)} prompts → {prompts_path}")
    print(f"\nFor each prompt, feed to a Claude Haiku subagent and collect the body text.")
    print(f"Then save the results with the contentId, contentType, body, and sortOrder fields.")

    # Check for existing results
    results_path = OUTPUT_DIR / f"{COLLECTION_SLUG}_chronicle_content.json"
    if results_path.exists():
        with open(results_path) as f:
            results = json.load(f)
        print(f"\nExisting results found: {len(results)} records")

        # Export to JSONL
        CONVEX_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path = CONVEX_EXPORT_DIR / f"{COLLECTION_PREFIX}ChronicleContent.jsonl"
        with open(export_path, "w", encoding="utf-8") as f:
            for record in results:
                clean = {k: v for k, v in record.items() if v is not None and k != "prompt"}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")
        print(f"Exported → {export_path}")


if __name__ == "__main__":
    main()
