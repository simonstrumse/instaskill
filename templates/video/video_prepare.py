"""
Phase 1: Video Preparation — Key Frame Extraction

Uses ffmpeg scene detection to extract representative frames from each video.
Falls back to uniform sampling if scene detection yields too few frames.

Input: video files in VIDEO_DIR
Output: FRAMES_DIR/{postId}/frame_*.jpg + batch manifest

Requires: ffmpeg installed (brew install ffmpeg)
"""

import json
import subprocess
from pathlib import Path

# ============ CONFIGURATION ============
# Default paths — override with --data-dir for collection-scoped directories
# e.g., --data-dir data/food  →  data/food/videos, data/food/video_frames, etc.
DATA_DIR = Path("data")
VIDEO_DIR = DATA_DIR / "videos"           # Directory containing video files
FRAMES_DIR = DATA_DIR / "video_frames"    # Output directory for key frames
MANIFEST_PATH = DATA_DIR / "video_manifest.json"
DEFAULT_FRAMES = 16                       # Frames per video
SCENE_THRESHOLD = 0.3                     # ffmpeg scene detection threshold
# =======================================


def get_video_files(video_dir):
    """Find all video files in the directory."""
    extensions = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
    return sorted(
        f for f in video_dir.iterdir()
        if f.suffix.lower() in extensions
    )


def extract_scene_frames(video_path, output_dir, max_frames):
    """Extract frames at scene changes using ffmpeg."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(output_dir / "scene_%04d.jpg")

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"select='gt(scene,{SCENE_THRESHOLD})',setpts=N/FRAME_RATE/TB",
        "-frames:v", str(max_frames * 2),  # Over-extract, then pick best
        "-vsync", "vfr",
        "-q:v", "2",
        pattern,
        "-y", "-loglevel", "error",
    ]

    subprocess.run(cmd, check=True)
    frames = sorted(output_dir.glob("scene_*.jpg"))
    return frames


def extract_uniform_frames(video_path, output_dir, num_frames):
    """Extract uniformly spaced frames as fallback."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip() or "0")
    if duration <= 0:
        return []

    interval = duration / (num_frames + 1)
    frames = []

    for i in range(1, num_frames + 1):
        timestamp = interval * i
        output = output_dir / f"frame_{i:04d}.jpg"
        cmd = [
            "ffmpeg", "-ss", str(timestamp), "-i", str(video_path),
            "-frames:v", "1", "-q:v", "2",
            str(output), "-y", "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True)
        if output.exists():
            frames.append(output)

    return frames


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract key frames from videos")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES, help="Frames per video")
    parser.add_argument("--limit", type=int, default=None, help="Max videos to process")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Base data directory (e.g., data/food for collection-scoped paths)")
    parser.add_argument("--video-dir", type=str, default=None)
    args = parser.parse_args()

    # Resolve paths: --data-dir sets the base, --video-dir overrides video location
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    video_dir = Path(args.video_dir) if args.video_dir else data_dir / "videos"
    frames_dir = data_dir / "video_frames"
    manifest_path = data_dir / "video_manifest.json"

    videos = get_video_files(video_dir)
    if args.limit:
        videos = videos[:args.limit]

    print(f"Found {len(videos)} videos in {video_dir}")
    print(f"Extracting {args.frames} frames per video")

    manifest = []
    for i, video in enumerate(videos):
        post_id = video.stem  # Assumes filename is {postId}.mp4
        output_dir = frames_dir / post_id
        print(f"  [{i+1}/{len(videos)}] {video.name}...", end=" ", flush=True)

        # Skip if already extracted
        if output_dir.exists() and len(list(output_dir.glob("*.jpg"))) >= args.frames // 2:
            frames = sorted(output_dir.glob("*.jpg"))
            print(f"cached ({len(frames)} frames)")
        else:
            try:
                frames = extract_scene_frames(video, output_dir, args.frames)
                if len(frames) < args.frames // 2:
                    frames = extract_uniform_frames(video, output_dir, args.frames)
                    print(f"uniform ({len(frames)} frames)")
                else:
                    # Keep only the requested number
                    if len(frames) > args.frames:
                        step = len(frames) / args.frames
                        frames = [frames[int(i * step)] for i in range(args.frames)]
                    print(f"scene ({len(frames)} frames)")
            except subprocess.CalledProcessError as e:
                print(f"ERROR: {e}")
                continue

        # Rename to standardized frame_NNNN.jpg
        final_frames = []
        for j, frame in enumerate(frames[:args.frames]):
            target = output_dir / f"frame_{j+1:04d}.jpg"
            if frame != target:
                frame.rename(target)
            final_frames.append(str(target))

        manifest.append({
            "postId": post_id,
            "videoPath": str(video),
            "framesDir": str(output_dir),
            "frameCount": len(final_frames),
            "framePaths": final_frames,
        })

    # Save manifest
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest: {len(manifest)} videos → {manifest_path}")


if __name__ == "__main__":
    main()
