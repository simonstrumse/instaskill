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

# Data files
DATA_FILES = {
    "instagram": {
        "saved_posts": DATA_DIR / "instagram" / "saved_posts.json",
    },
}

# Rate limiting defaults (requests per minute)
RATE_LIMITS = {
    "instagram": 30,
}

# Platform credentials
PLATFORM_CREDENTIALS = {
    "instagram": CREDENTIALS_DIR / "instagram" / "session.json",
}

# Sync state file
SYNC_STATE_FILE = DATA_DIR / "sync_state.json"


def ensure_dirs() -> None:
    """Create all required directories if they don't exist."""
    for d in [DATA_DIR, CREDENTIALS_DIR, LEGACY_DIR, MEDIA_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "instagram").mkdir(parents=True, exist_ok=True)
    PLATFORM_CREDENTIALS["instagram"].parent.mkdir(parents=True, exist_ok=True)
