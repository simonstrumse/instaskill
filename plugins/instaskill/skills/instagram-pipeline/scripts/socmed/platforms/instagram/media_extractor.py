"""Extract textual information from downloaded Instagram media.

Uses Whisper (via lightning-whisper-mlx) for audio transcription from videos,
and ocrmac (macOS Vision framework) for on-screen text extraction from both
video frames and images.

Designed for resumability: each processed post gets an `extracted_text` field
in the JSON store. Posts with this field are skipped on re-run, so the
pipeline survives session compaction and incremental media downloads.

Usage:
    .venv/bin/python3 -m socmed.platforms.instagram.media_extractor run
    .venv/bin/python3 -m socmed.platforms.instagram.media_extractor run --collection Matinspo
    .venv/bin/python3 -m socmed.platforms.instagram.media_extractor run --limit 50
    .venv/bin/python3 -m socmed.platforms.instagram.media_extractor stats
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from socmed.config import DATA_FILES
from socmed.storage.json_store import JsonStore

logger = logging.getLogger(__name__)

# Frame sampling interval for video OCR (seconds)
FRAME_INTERVAL_SECS = 3.0

# Minimum OCR confidence to include a text result
MIN_OCR_CONFIDENCE = 0.5

# Minimum text length to keep (filters out single-char noise)
MIN_TEXT_LENGTH = 2


def _load_whisper():
    """Load the Whisper model once. Returns the model instance.

    Uses large-v3 for multilingual support (needed for Norwegian recipe content).
    The model takes ~10-15s to load but is then reused for all videos.
    """
    from lightning_whisper_mlx import LightningWhisperMLX

    return LightningWhisperMLX(model="large-v3", batch_size=12)


def extract_audio_from_video(video_path: str | Path) -> str | None:
    """Extract audio track from a video file to a temporary WAV file.

    Uses ffmpeg to extract and convert audio to 16kHz mono WAV,
    which is what Whisper expects.

    Returns path to temp WAV file, or None if extraction fails.
    The caller is responsible for cleaning up the temp file.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return None

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",                  # No video
                "-acodec", "pcm_s16le", # 16-bit PCM
                "-ar", "16000",         # 16kHz (Whisper's expected rate)
                "-ac", "1",             # Mono
                tmp.name,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            Path(tmp.name).unlink(missing_ok=True)
            return None
        # Check the output file has actual content
        if Path(tmp.name).stat().st_size < 1000:
            Path(tmp.name).unlink(missing_ok=True)
            return None
        return tmp.name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        Path(tmp.name).unlink(missing_ok=True)
        return None


def transcribe_audio(whisper_model, audio_path: str) -> str:
    """Transcribe an audio file using Whisper.

    Returns the transcribed text, or empty string on failure.
    """
    try:
        result = whisper_model.transcribe(audio_path)
        return (result.get("text") or "").strip()
    except Exception as e:
        logger.warning(f"Whisper transcription failed: {e}")
        return ""


def extract_video_frames(video_path: str | Path, interval: float = FRAME_INTERVAL_SECS) -> list[str]:
    """Extract frames from a video at regular intervals.

    Returns list of paths to temporary frame image files.
    The caller is responsible for cleaning up the temp files.
    """
    import cv2

    video_path = str(video_path)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    # Calculate which frames to extract
    frame_interval = int(fps * interval)
    if frame_interval < 1:
        frame_interval = 1

    frame_paths = []
    frame_idx = 0

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        cv2.imwrite(tmp.name, frame)
        frame_paths.append(tmp.name)

        frame_idx += frame_interval
        if frame_idx >= total_frames:
            break

    cap.release()
    return frame_paths


def ocr_image(image_path: str | Path) -> list[tuple[str, float]]:
    """Run OCR on a single image using macOS Vision framework.

    Returns list of (text, confidence) tuples.
    """
    from ocrmac.ocrmac import OCR

    try:
        result = OCR(str(image_path), recognition_level="accurate")
        annotations = result.recognize()
        return [
            (text, conf)
            for text, conf, _bbox in annotations
            if conf >= MIN_OCR_CONFIDENCE and len(text.strip()) >= MIN_TEXT_LENGTH
        ]
    except Exception as e:
        logger.warning(f"OCR failed on {image_path}: {e}")
        return []


def deduplicate_ocr_texts(texts: list[tuple[str, float]]) -> list[str]:
    """Deduplicate OCR results across multiple frames/images.

    Video frames often contain the same text across many consecutive frames.
    This normalizes and deduplicates while preserving the highest-confidence version.
    """
    seen: dict[str, tuple[str, float]] = {}  # normalized -> (original, confidence)

    for text, conf in texts:
        normalized = text.strip().lower()
        if not normalized:
            continue
        if normalized not in seen or conf > seen[normalized][1]:
            seen[normalized] = (text.strip(), conf)

    # Sort by confidence descending, return original (non-normalized) texts
    sorted_texts = sorted(seen.values(), key=lambda x: x[1], reverse=True)
    return [t for t, _c in sorted_texts]


def process_video(
    video_path: str | Path,
    whisper_model,
) -> dict:
    """Process a single video file: transcribe audio + OCR frames.

    Returns dict with:
        audio_transcript: str
        ocr_texts: list[str]
        duration_secs: float
    """
    import cv2

    video_path = Path(video_path)
    result = {"audio_transcript": "", "ocr_texts": [], "duration_secs": 0.0}

    if not video_path.exists():
        return result

    # Get video duration
    cap = cv2.VideoCapture(str(video_path))
    if cap.isOpened():
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        result["duration_secs"] = round(total_frames / fps, 1) if fps > 0 else 0
        cap.release()

    # Audio transcription
    audio_path = extract_audio_from_video(video_path)
    if audio_path:
        try:
            result["audio_transcript"] = transcribe_audio(whisper_model, audio_path)
        finally:
            Path(audio_path).unlink(missing_ok=True)

    # Frame OCR
    frame_paths = extract_video_frames(video_path)
    all_ocr: list[tuple[str, float]] = []
    try:
        for fp in frame_paths:
            all_ocr.extend(ocr_image(fp))
    finally:
        for fp in frame_paths:
            Path(fp).unlink(missing_ok=True)

    result["ocr_texts"] = deduplicate_ocr_texts(all_ocr)
    return result


def process_image(image_path: str | Path) -> dict:
    """Process a single image file: OCR extraction.

    Returns dict with:
        ocr_texts: list[str]
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return {"ocr_texts": []}

    raw = ocr_image(image_path)
    return {"ocr_texts": deduplicate_ocr_texts(raw)}


def get_extractable_posts(
    collection: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Find posts that have local media but no extraction yet.

    Only returns posts where at least one media item has a local_path.
    Skips posts that already have an `extracted_text` field.
    """
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    posts = store.read()
    candidates = []

    for post in posts:
        # Skip if already extracted
        if post.get("extracted_text"):
            continue

        # Must have at least one local media file
        has_local = any(m.get("local_path") for m in post.get("media", []))
        if not has_local:
            continue

        # Collection filter
        if collection:
            post_cols = post.get("collections", [])
            if not any(collection.lower() in c.lower() for c in post_cols):
                continue

        candidates.append(post)
        if limit and len(candidates) >= limit:
            break

    return candidates


def run_extraction(
    collection: str | None = None,
    limit: int | None = None,
    save_every: int = 10,
    skip_whisper: bool = False,
    skip_ocr: bool = False,
):
    """Run the full extraction pipeline.

    Args:
        collection: Only process posts in this collection (substring match).
        limit: Max posts to process.
        save_every: Save progress every N posts.
        skip_whisper: Skip audio transcription (OCR only).
        skip_ocr: Skip OCR (audio only).
    """
    candidates = get_extractable_posts(collection=collection, limit=limit)
    if not candidates:
        print("No posts need text extraction.")
        return

    col_str = f" in \"{collection}\"" if collection else ""
    print(f"Found {len(candidates)} posts{col_str} needing extraction")

    # Count media types
    n_videos = sum(
        1 for p in candidates
        for m in p.get("media", [])
        if m.get("media_type") == "video" and m.get("local_path")
    )
    n_images = sum(
        1 for p in candidates
        for m in p.get("media", [])
        if m.get("media_type") == "image" and m.get("local_path")
    )
    print(f"  Videos to process: {n_videos}")
    print(f"  Images to process: {n_images}")

    # Load Whisper model once (expensive — ~10-15s)
    whisper_model = None
    if not skip_whisper and n_videos > 0:
        print("\nLoading Whisper large-v3 model...")
        t0 = time.time()
        whisper_model = _load_whisper()
        print(f"Model loaded in {time.time() - t0:.1f}s")
    elif skip_whisper:
        print("\nSkipping audio transcription (--skip-whisper)")

    if skip_ocr:
        print("Skipping OCR (--skip-ocr)")

    print()

    # Use patch_items for concurrent-safe writes — only updates extracted_text
    # field, never clobbering enrichment data written by browser_enricher.
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    pending_patches: dict[str, dict] = {}

    processed = 0
    videos_transcribed = 0
    images_ocrd = 0
    total_audio_secs = 0
    start_time = time.time()

    for ci, candidate in enumerate(candidates):
        post_id = candidate["id"]

        extraction = {
            "audio_transcripts": [],
            "ocr_texts": [],
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extraction_status": "complete",
        }

        post_ocr_all: list[tuple[str, float]] = []

        for m in candidate.get("media", []):
            local_path = m.get("local_path")
            if not local_path or not Path(local_path).exists():
                continue

            if m.get("media_type") == "video":
                vid_result = process_video(
                    local_path,
                    whisper_model=whisper_model,
                )
                if vid_result["audio_transcript"] and not skip_whisper:
                    extraction["audio_transcripts"].append(vid_result["audio_transcript"])
                    videos_transcribed += 1
                    total_audio_secs += vid_result["duration_secs"]

                if not skip_ocr:
                    # Collect raw OCR for dedup across all media
                    for t in vid_result["ocr_texts"]:
                        post_ocr_all.append((t, 1.0))

            elif m.get("media_type") == "image":
                if not skip_ocr:
                    raw = ocr_image(local_path)
                    post_ocr_all.extend(raw)
                    images_ocrd += 1

        # Deduplicate OCR across all media items in this post
        extraction["ocr_texts"] = deduplicate_ocr_texts(post_ocr_all)

        # Mark as partial if we skipped something
        if skip_whisper and n_videos > 0:
            extraction["extraction_status"] = "partial:no_audio"
        if skip_ocr:
            extraction["extraction_status"] = "partial:no_ocr"

        pending_patches[post_id] = {"extracted_text": extraction}
        processed += 1

        # Progress indicator
        has_audio = bool(extraction["audio_transcripts"])
        has_ocr = bool(extraction["ocr_texts"])
        indicator = "A" if has_audio and has_ocr else "a" if has_audio else "T" if has_ocr else "."
        sys.stdout.write(indicator)
        sys.stdout.flush()

        # Periodic save — merge only extracted_text into current file
        if processed % save_every == 0 or ci == len(candidates) - 1:
            store.patch_items(pending_patches)
            pending_patches.clear()
            elapsed = time.time() - start_time
            rate = processed / elapsed * 60 if elapsed > 0 else 0
            remaining = len(candidates) - (ci + 1)
            eta = remaining / (rate / 60) if rate > 0 else 0
            print(f" [{ci+1}/{len(candidates)}] "
                  f"{videos_transcribed} transcribed, "
                  f"{images_ocrd} OCR'd | "
                  f"{rate:.1f}/min | "
                  f"ETA: {eta/60:.1f}min")

    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"Extraction complete in {elapsed/60:.1f} minutes")
    print(f"  Posts processed: {processed}")
    print(f"  Videos transcribed: {videos_transcribed} ({total_audio_secs:.0f}s of audio)")
    print(f"  Images OCR'd: {images_ocrd}")

    # Summary of content found (re-read file for accurate counts)
    all_posts = store.read()
    total_transcripts = sum(
        len(p.get("extracted_text", {}).get("audio_transcripts", []))
        for p in all_posts if p.get("extracted_text")
    )
    total_ocr = sum(
        len(p.get("extracted_text", {}).get("ocr_texts", []))
        for p in all_posts if p.get("extracted_text")
    )
    print(f"  Total audio transcripts: {total_transcripts}")
    print(f"  Total unique OCR texts: {total_ocr}")


def show_stats():
    """Show extraction statistics."""
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    posts = store.read()

    total = len(posts)
    with_extraction = sum(1 for p in posts if p.get("extracted_text"))
    with_audio = sum(
        1 for p in posts
        if p.get("extracted_text", {}).get("audio_transcripts")
    )
    with_ocr = sum(
        1 for p in posts
        if p.get("extracted_text", {}).get("ocr_texts")
    )

    # How many still need extraction
    with_local_media = sum(
        1 for p in posts
        if any(m.get("local_path") for m in p.get("media", []))
    )
    pending = with_local_media - with_extraction

    print(f"Total posts:           {total}")
    print(f"With local media:      {with_local_media}")
    print(f"Extracted:             {with_extraction}")
    print(f"  With audio:          {with_audio}")
    print(f"  With OCR text:       {with_ocr}")
    print(f"Pending extraction:    {pending}")

    # Collection breakdown
    collections: dict[str, dict] = {}
    for p in posts:
        for c in p.get("collections", []):
            if c not in collections:
                collections[c] = {"total": 0, "extracted": 0, "pending": 0}
            collections[c]["total"] += 1
            if p.get("extracted_text"):
                collections[c]["extracted"] += 1
            elif any(m.get("local_path") for m in p.get("media", [])):
                collections[c]["pending"] += 1

    if collections:
        print(f"\nBy collection (top 15):")
        sorted_cols = sorted(collections.items(), key=lambda x: x[1]["pending"], reverse=True)
        for name, counts in sorted_cols[:15]:
            print(f"  {name}: {counts['extracted']}/{counts['total']} extracted, "
                  f"{counts['pending']} pending")


def show_sample(post_id: str | None = None, collection: str | None = None):
    """Show extraction results for a specific post or random extracted post."""
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    posts = store.read()

    target = None
    if post_id:
        for p in posts:
            if p["id"] == post_id:
                target = p
                break
    else:
        for p in posts:
            if not p.get("extracted_text"):
                continue
            if collection:
                if not any(collection.lower() in c.lower() for c in p.get("collections", [])):
                    continue
            # Prefer one with both audio and OCR
            et = p["extracted_text"]
            if et.get("audio_transcripts") and et.get("ocr_texts"):
                target = p
                break
        if not target:
            # Fall back to any extracted post
            for p in posts:
                if p.get("extracted_text"):
                    if collection:
                        if not any(collection.lower() in c.lower() for c in p.get("collections", [])):
                            continue
                    target = p
                    break

    if not target:
        print("No extracted posts found.")
        return

    print(f"Post: {target['id']} by @{target.get('author', {}).get('username', '?')}")
    print(f"URL: {target.get('post_url', '?')}")
    print(f"Collections: {', '.join(target.get('collections', []))}")
    print(f"\n--- Caption ---")
    print(target.get("text", "[No caption]")[:500])

    et = target.get("extracted_text", {})
    if et.get("audio_transcripts"):
        for i, t in enumerate(et["audio_transcripts"]):
            print(f"\n--- Audio Transcript {i+1} ---")
            print(t[:500])

    if et.get("ocr_texts"):
        print(f"\n--- OCR Texts ({len(et['ocr_texts'])} unique) ---")
        for t in et["ocr_texts"][:20]:
            print(f"  {t}")

    print(f"\nExtracted at: {et.get('extracted_at', '?')}")
    print(f"Status: {et.get('extraction_status', '?')}")


def main():
    """CLI entry point."""
    import argparse

    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Extract text from Instagram media (Whisper + OCR)"
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run extraction pipeline")
    run_parser.add_argument("--collection", type=str, default=None,
                            help="Only extract from this collection (substring match)")
    run_parser.add_argument("--limit", type=int, default=None,
                            help="Max posts to process")
    run_parser.add_argument("--save-every", type=int, default=10,
                            help="Save progress every N posts (default: 10)")
    run_parser.add_argument("--skip-whisper", action="store_true",
                            help="Skip audio transcription (OCR only)")
    run_parser.add_argument("--skip-ocr", action="store_true",
                            help="Skip OCR (audio transcription only)")

    sub.add_parser("stats", help="Show extraction statistics")

    sample_parser = sub.add_parser("sample", help="Show extraction results for a post")
    sample_parser.add_argument("--post-id", type=str, default=None,
                               help="Specific post shortcode")
    sample_parser.add_argument("--collection", type=str, default=None,
                               help="Show sample from this collection")

    args = parser.parse_args()

    if args.command == "run":
        run_extraction(
            collection=args.collection,
            limit=args.limit,
            save_every=args.save_every,
            skip_whisper=args.skip_whisper,
            skip_ocr=args.skip_ocr,
        )
    elif args.command == "stats":
        show_stats()
    elif args.command == "sample":
        show_sample(post_id=args.post_id, collection=args.collection)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
