"""Paths, constants, and platform registry.

When bundled as a skill, the data directory defaults to the current working
directory (where the user runs the pipeline). Override with SOCMED_DATA_DIR
environment variable for explicit control.
"""

import os
from pathlib import Path

# Data directory: configurable for portability
# Priority: SOCMED_DATA_DIR env var > auto-detect > current directory
_auto_root = Path(__file__).resolve().parent.parent
_has_data_dir = (_auto_root / "data").exists()

PROJECT_ROOT = Path(
    os.environ.get("SOCMED_DATA_DIR", str(_auto_root if _has_data_dir else Path.cwd()))
)

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
LEGACY_DIR = PROJECT_ROOT / "legacy"
MEDIA_DIR = DATA_DIR / "media"

# Per-platform data paths
PLATFORM_DATA = {
    "threads": DATA_DIR / "threads",
    "linkedin": DATA_DIR / "linkedin",
    "instagram": DATA_DIR / "instagram",
}

# Per-platform credential paths
PLATFORM_CREDENTIALS = {
    "instagram": CREDENTIALS_DIR / "instagram" / "session.json",
    "linkedin": CREDENTIALS_DIR / "linkedin" / "cookies.json",
    "threads": CREDENTIALS_DIR / "threads" / "account.json",
}

# Sync state file
SYNC_STATE_FILE = DATA_DIR / "sync_state.json"

# Data files per platform
DATA_FILES = {
    "threads": {
        "saved_posts": DATA_DIR / "threads" / "saved_posts.json",
    },
    "linkedin": {
        "saved_posts": DATA_DIR / "linkedin" / "saved_posts.json",
        "conversations": DATA_DIR / "linkedin" / "conversations.json",
    },
    "instagram": {
        "saved_posts": DATA_DIR / "instagram" / "saved_posts.json",
        "conversations": DATA_DIR / "instagram" / "conversations.json",
    },
}

# Rate limiting defaults (requests per minute)
RATE_LIMITS = {
    "threads": 30,
    "linkedin": 20,
    "instagram": 30,
    "apify": 60,
}

# Supported platforms
PLATFORMS = ["threads", "linkedin", "instagram"]

# Content types per platform
CONTENT_TYPES = {
    "threads": ["saved"],
    "linkedin": ["saved", "messages"],
    "instagram": ["saved", "messages"],
}


def ensure_dirs() -> None:
    """Create all required directories if they don't exist."""
    for d in [DATA_DIR, CREDENTIALS_DIR, LEGACY_DIR, MEDIA_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    for platform_dir in PLATFORM_DATA.values():
        platform_dir.mkdir(parents=True, exist_ok=True)
    for cred_path in PLATFORM_CREDENTIALS.values():
        cred_path.parent.mkdir(parents=True, exist_ok=True)
