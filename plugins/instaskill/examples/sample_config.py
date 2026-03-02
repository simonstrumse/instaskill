"""
Sample config.py for a fictional "Climate" collection deep dive.

Copy this file to your project's deep-dive directory and customize.
The agent will import these values from config.py in every template script.

Usage: cp examples/sample_config.py your-collection/config.py
"""

from pathlib import Path

# =============================================================================
# COLLECTION IDENTITY
# =============================================================================

COLLECTION_NAME = "Climate"                 # Human-readable name
COLLECTION_SLUG = "climate"                 # URL path segment: /climate/chronicle
COLLECTION_PREFIX = "climate"               # Convex table prefix: climateTimeline, climateChapters, etc.

# Instagram collection name(s) — exact match from saved_posts.json
# Some collections have multiple variant names (e.g., renamed over time)
COLLECTION_FILTER_NAMES = ["Climate & Environment", "Climate"]

# =============================================================================
# PATHS — Adjust BASE to your project root
# =============================================================================

BASE = Path(__file__).parent.parent         # Assumes scripts are in {project}/{collection}/
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

# Choose ONE approach:
#   "alias"   — for collections about named figures (politics, conflict, media)
#   "account" — for collections about creators (food, art, tutorials)
ENTITY_APPROACH = "alias"

# Alias table: canonical_name → [aliases]
# Start empty. Populated during Step 2 by inspecting your data.
# The agent will help build this by scanning post text.
ALIAS_TABLE = {
    # Example entries (replace with your collection's entities):
    # "Greta Thunberg": ["Greta", "Thunberg", "gretathunberg"],
    # "IPCC": ["IPCC", "Intergovernmental Panel on Climate Change"],
    # "COP28": ["COP28", "COP 28", "Dubai climate summit"],
}

# Entity metadata: canonical_name → {role, affiliation, ...}
# Optional. Enriches person profiles with context the agent can't infer.
ENTITY_METADATA = {
    # "Greta Thunberg": {
    #     "role": "activist",
    #     "affiliation": "Fridays for Future",
    #     "description_hint": "Swedish climate activist",
    # },
}

# Fuzzy matching threshold (0-100). Lower = more matches, more noise.
FUZZY_MATCH_THRESHOLD = 85

# =============================================================================
# EVENT DETECTION (Step 3)
# =============================================================================

# Aggregation level: "daily" for large collections (>500 posts), "weekly" for small (<300)
EVENT_AGGREGATION = "daily"

# Z-score threshold: 2.0 for large collections, 1.5 for small/noisy ones
EVENT_Z_THRESHOLD = 2.0

# PELT changepoint penalty: higher = fewer changepoints. Start at 10, tune down if too few events.
EVENT_PELT_PENALTY = 10

# Context window (days): how many days around a burst to look for context
EVENT_CONTEXT_WINDOW = 1

# =============================================================================
# ACCOUNT CLASSIFICATION (Step 4)
# =============================================================================

# Account type taxonomy — these emerge from YOUR data during Step 4.
# The agent discovers types by sampling top accounts. Start with a generic set.
ACCOUNT_TYPES = [
    "news_org",
    "activist",
    "researcher",
    "creator",
    "institutional",
    "commentary",
    "other",
]

# Top N accounts to classify via LLM (rest use cosine similarity to centroids)
ACCOUNT_LLM_TOP_N = 50

# =============================================================================
# NARRATIVE CLASSIFICATION (Step 5)
# =============================================================================

# Narrative frames — these MUST emerge from your data.
# Start empty. The agent runs discovery mode: samples 200 posts, identifies recurring frames.
NARRATIVE_FRAMES = [
    # Example frames (replace with your collection's frames):
    # "climate_justice",
    # "scientific_evidence",
    # "corporate_accountability",
    # "individual_action",
    # "policy_advocacy",
    # "doom_and_gloom",
    # "hope_and_solutions",
]

# =============================================================================
# CLAIM EXTRACTION (Step 6)
# =============================================================================

# Claim categories — domain-specific types of factual claims to extract.
CLAIM_CATEGORIES = [
    # Example categories:
    # "temperature",        # Temperature records, projections
    # "emissions",          # CO2/methane data
    # "policy",             # Government actions, legislation
    # "impact",             # Effects on ecosystems, communities
    # "corporate",          # Company commitments, greenwashing
    # "timeline",           # Deadlines, projections (e.g., "by 2030")
]

# =============================================================================
# CHAPTERS (Step 7)
# =============================================================================

# Chapters are defined MANUALLY after reviewing event detection output.
# The agent will help you identify natural breakpoints.
# Format: {"id": "ch_01", "title": "...", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
CHAPTERS = [
    # Populated during Step 7. Example:
    # {"id": "ch_01", "title": "Early Awareness", "start": "2020-01-01", "end": "2021-06-30"},
    # {"id": "ch_02", "title": "COP26 Surge", "start": "2021-07-01", "end": "2022-03-31"},
]

# =============================================================================
# PROFILE TIERS (Step 9)
# =============================================================================

# Person profiles (alias-based entities)
PERSON_FULL_TIER = 10   # ≥10 posts → full profile page with bio, timeline, post grid
PERSON_CHIP_TIER = 3    # 3-9 posts → chip profile (name, count, link)

# Account profiles (Instagram accounts)
ACCOUNT_FULL_TIER = 5   # ≥5 posts → full creator page
ACCOUNT_CHIP_TIER = 2   # 2-4 posts → chip profile

# For small collections (<300 posts), lower these:
# PERSON_FULL_TIER = 3
# PERSON_CHIP_TIER = 2
# ACCOUNT_FULL_TIER = 3
# ACCOUNT_CHIP_TIER = 1

# =============================================================================
# CROSS-COLLECTION (Optional)
# =============================================================================

# Other collections to check for double-saved posts.
# Format: {"label": "Collection Name in saved_posts.json"}
DOUBLE_SAVE_TARGETS = {
    # "golden": "Golden inspirational",
    # "anarchy": "Anarchy",
}
