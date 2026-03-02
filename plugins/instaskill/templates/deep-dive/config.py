"""
Deep Dive Configuration — Shared by all template scripts.

Copy this file to your project directory and customize for your collection.
Every template script imports: `from config import *`

See examples/sample_config.py for a fully annotated version with a fictional collection.
"""

from pathlib import Path

# =============================================================================
# COLLECTION IDENTITY
# =============================================================================

COLLECTION_NAME = "YourCollection"          # Human-readable name
COLLECTION_SLUG = "your-collection"         # URL path: /{slug}/chronicle
COLLECTION_PREFIX = "yourCollection"        # Convex table prefix (camelCase)

# Exact collection name(s) from saved_posts.json → post["collections"]
COLLECTION_FILTER_NAMES = ["YourCollection"]

# =============================================================================
# PATHS — Adjust BASE to your project root
# =============================================================================

BASE = Path(__file__).parent.parent         # Assumes deep-dive scripts are in {project}/{collection}/
DATA = BASE / "data"

# Global inputs (from instagram-analysis pipeline)
POSTS_JSON = DATA / "instagram" / "saved_posts.json"
POST_IDS_JSON = DATA / "post_ids.json"
EMBEDDINGS_NPY = DATA / "embeddings.npy"
TOPICS_JSON = DATA / "topic_assignments.json"
SENTIMENT_JSON = DATA / "sentiment_scores.json"

# Collection outputs
OUTPUT_DIR = DATA / COLLECTION_SLUG
CONVEX_EXPORT_DIR = OUTPUT_DIR / "convex_export"

# Derived paths (used by individual scripts)
OUTPUT_POSTS = OUTPUT_DIR / f"{COLLECTION_SLUG}_posts.json"
OUTPUT_EMBEDDINGS = OUTPUT_DIR / f"{COLLECTION_SLUG}_embeddings.npy"
OUTPUT_POST_IDS = OUTPUT_DIR / f"{COLLECTION_SLUG}_post_ids.json"

# =============================================================================
# ENTITY EXTRACTION (Step 2)
# =============================================================================

# "alias" for figure-heavy collections, "account" for creator-heavy
ENTITY_APPROACH = "alias"  # or "account"

# Alias table: canonical → [variants]. Populated during Step 2.
ALIAS_TABLE = {}

# Entity metadata: canonical → {role, affiliation, ...}. Optional enrichment.
ENTITY_METADATA = {}

# Fuzzy matching threshold for alias lookup (0-100)
FUZZY_MATCH_THRESHOLD = 85

# =============================================================================
# EVENT DETECTION (Step 3)
# =============================================================================

EVENT_AGGREGATION = "daily"     # "daily" for >500 posts, "weekly" for <300
EVENT_Z_THRESHOLD = 2.0         # Lower to 1.5 for small/noisy collections
EVENT_PELT_PENALTY = 10         # Higher = fewer changepoints
EVENT_CONTEXT_WINDOW = 1        # Days around burst for fingerprinting

# =============================================================================
# ACCOUNT CLASSIFICATION (Step 4)
# =============================================================================

# Starting taxonomy — the agent discovers actual types from your data.
ACCOUNT_TYPES = [
    "news_org", "activist", "creator", "commentary", "institutional", "other",
]
ACCOUNT_LLM_TOP_N = 50         # Top N accounts classified by LLM

# =============================================================================
# NARRATIVE CLASSIFICATION (Step 5)
# =============================================================================

# Frames emerge from your data. Start empty; the agent runs discovery mode.
NARRATIVE_FRAMES = []

# =============================================================================
# CLAIM EXTRACTION (Step 6)
# =============================================================================

CLAIM_CATEGORIES = []           # Domain-specific claim types

# =============================================================================
# CHAPTERS (Step 7)
# =============================================================================

# Defined manually after reviewing event detection output.
CHAPTERS = []  # [{"id": "ch_01", "title": "...", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}]

# =============================================================================
# PROFILE TIERS (Step 9)
# =============================================================================

PERSON_FULL_TIER = 10           # >=N posts → full profile page
PERSON_CHIP_TIER = 3            # N–M posts → chip profile

ACCOUNT_FULL_TIER = 5           # >=N posts → full creator page
ACCOUNT_CHIP_TIER = 2           # N–M posts → chip profile

# =============================================================================
# CROSS-COLLECTION
# =============================================================================

# Other collections to check for double-saved posts.
DOUBLE_SAVE_TARGETS = {}  # {"label": "Collection Name in saved_posts.json"}
