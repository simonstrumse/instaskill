"""Bootstrap Instagram saved posts directly from the API — no archive download needed.

Fetches saved posts and collection metadata using Chrome's session cookies,
producing the same saved_posts.json format as archive import + enrichment.
Posts come pre-enriched (captions, media URLs, author info, timestamps)
so they skip straight to extraction (Whisper + OCR).

Usage:
    .venv/bin/python3 -m socmed.platforms.instagram.api_bootstrap sync
    .venv/bin/python3 -m socmed.platforms.instagram.api_bootstrap sync --collection Hundetriks
    .venv/bin/python3 -m socmed.platforms.instagram.api_bootstrap sync --limit 100
    .venv/bin/python3 -m socmed.platforms.instagram.api_bootstrap collections
    .venv/bin/python3 -m socmed.platforms.instagram.api_bootstrap stats
"""

from __future__ import annotations

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

from socmed.config import DATA_FILES, MEDIA_DIR
from socmed.platforms.instagram.browser_enricher import (
    _extract_media_from_item,
    build_session,
    download_post_media,
    get_chrome_cookies,
)
from socmed.storage.json_store import JsonStore
from socmed.storage.sync_tracker import SyncTracker

logger = logging.getLogger(__name__)

# API endpoints
COLLECTIONS_URL = "https://www.instagram.com/api/v1/collections/list/"
SAVED_FEED_URL = "https://www.instagram.com/api/v1/feed/saved/posts/"


def fetch_collections(session: requests.Session) -> list[dict]:
    """Fetch all saved collections with names and IDs.

    Returns list of dicts with: id, name, count.
    Paginates automatically if more_available.
    """
    collections = []
    max_id = None

    while True:
        params = {}
        if max_id:
            params["max_id"] = max_id

        resp = session.get(COLLECTIONS_URL, params=params, timeout=15)
        if resp.status_code != 200:
            logger.error(f"Collections list failed: {resp.status_code}")
            break

        data = resp.json()
        for item in data.get("items", []):
            collections.append({
                "id": str(item.get("collection_id", "")),
                "name": item.get("collection_name", ""),
                "count": item.get("collection_media_count", 0),
            })

        if not data.get("more_available"):
            break
        max_id = data.get("next_max_id")
        time.sleep(1)

    return collections


def _media_type_to_content_type(media_type: int) -> str:
    """Map Instagram media_type int to our content_type string."""
    # 1 = photo, 2 = video/reel, 8 = carousel
    if media_type == 2:
        return "reel"
    return "saved_post"


def _api_item_to_post(
    item: dict,
    collection_map: dict[str, str],
) -> dict:
    """Convert an API saved feed item to our unified post format.

    The item comes from /api/v1/feed/saved/posts/ and contains a 'media' key
    with the full post data. Each post self-reports its collection membership
    via saved_collection_ids.

    Args:
        item: Raw API item (has 'media' key).
        collection_map: Maps collection ID -> collection name.

    Returns:
        Post dict matching our saved_posts.json schema.
    """
    media = item.get("media", item)

    shortcode = media.get("code", "")
    if not shortcode:
        return None

    user = media.get("user", {})
    username = user.get("username", "")
    display_name = user.get("full_name", "")

    # Caption
    caption_text = ""
    caption_obj = media.get("caption")
    if caption_obj and isinstance(caption_obj, dict):
        caption_text = caption_obj.get("text", "")

    # Content type from media_type
    media_type_int = media.get("media_type", 1)
    content_type = _media_type_to_content_type(media_type_int)

    # Extract media URLs using shared helper
    media_items = _extract_media_from_item(media)
    media_list = [
        {
            "url": m.get("url", ""),
            "media_type": m.get("type", "image"),
            "local_path": "",
            "alt_text": "",
            "width": m.get("w", 0),
            "height": m.get("h", 0),
        }
        for m in media_items
    ]

    # Timestamps
    created_at = ""
    taken_at = media.get("taken_at", 0)
    if taken_at:
        created_at = datetime.fromtimestamp(taken_at, tz=timezone.utc).isoformat()

    # Collection membership
    collection_ids = media.get("saved_collection_ids", [])
    collections = []
    for cid in collection_ids:
        name = collection_map.get(str(cid))
        if name:
            collections.append(name)

    # Post URL
    post_url = f"https://www.instagram.com/p/{shortcode}/"
    if content_type == "reel":
        post_url = f"https://www.instagram.com/reel/{shortcode}/"

    return {
        "id": shortcode,
        "platform": "instagram",
        "content_type": content_type,
        "text": caption_text or "[No caption]",
        "author": {
            "username": username,
            "display_name": display_name,
            "profile_url": f"https://www.instagram.com/{username}/" if username else "",
            "headline": "",
        },
        "media": media_list,
        "post_url": post_url,
        "created_at": created_at,
        "saved_at": datetime.now(tz=timezone.utc).isoformat(),
        "harvested_at": datetime.now(tz=timezone.utc).isoformat(),
        "like_count": media.get("like_count", 0),
        "reply_count": media.get("comment_count", 0),
        "repost_count": 0,
        "source": "archive+api",  # Already enriched from API
        "collections": collections,
        "media_pk": str(media.get("pk", "")),
    }


def fetch_saved_posts(
    session: requests.Session,
    collection_map: dict[str, str],
    limit: int | None = None,
    delay: float = 2.0,
    collection_filter: str | None = None,
) -> list[dict]:
    """Paginate through the saved posts feed and convert to post dicts.

    Args:
        session: Authenticated Instagram session.
        collection_map: Maps collection ID -> name (from fetch_collections).
        limit: Max posts to fetch (None = all).
        delay: Seconds between page requests.
        collection_filter: Only include posts in this collection (substring match).

    Returns:
        List of post dicts in saved_posts.json format.
    """
    posts = []
    max_id = None
    page = 0

    while True:
        params = {}
        if max_id:
            params["max_id"] = max_id

        resp = session.get(SAVED_FEED_URL, params=params, timeout=15)
        if resp.status_code != 200:
            logger.error(f"Saved feed failed: {resp.status_code}")
            break

        data = resp.json()
        items = data.get("items", [])
        page += 1

        for item in items:
            post = _api_item_to_post(item, collection_map)
            if not post:
                continue

            # Apply collection filter
            if collection_filter:
                post_cols = post.get("collections", [])
                if not any(collection_filter.lower() in c.lower() for c in post_cols):
                    continue

            posts.append(post)

            if limit and len(posts) >= limit:
                return posts

        sys.stdout.write(f"\r  Fetched {len(posts)} posts ({page} pages)...")
        sys.stdout.flush()

        if not data.get("more_available"):
            break
        max_id = data.get("next_max_id")
        time.sleep(delay)

    print()  # Newline after progress
    return posts


def run_sync(
    limit: int | None = None,
    delay: float = 2.0,
    download_media: bool = True,
    collection_filter: str | None = None,
    save_every: int = 100,
):
    """Sync saved posts from Instagram API into saved_posts.json.

    Fetches all saved posts via the API, maps collection IDs to names,
    and merges into the existing data store. Posts arrive pre-enriched
    so they're immediately ready for extraction.

    New posts are appended; existing posts are skipped (by shortcode).

    Args:
        limit: Max posts to fetch (None = all).
        delay: Seconds between API requests.
        download_media: Download media files alongside metadata.
        collection_filter: Only sync posts in this collection (substring match).
        save_every: Save progress every N posts.
    """
    print("Loading Chrome cookies...")
    cookies = get_chrome_cookies()
    session = build_session(cookies)
    user_id = cookies.get("ds_user_id", "?")
    print(f"Authenticated as user {user_id}")

    # Step 1: Fetch collections for ID -> name mapping
    print("\nFetching collections...")
    collections = fetch_collections(session)
    if not collections:
        print("No collections found. Make sure you're logged into Instagram in Chrome.")
        sys.exit(1)

    collection_map = {c["id"]: c["name"] for c in collections}
    total_saved = sum(c["count"] for c in collections)

    print(f"Found {len(collections)} collections ({total_saved} total posts):")
    for c in collections:
        marker = ""
        if collection_filter and collection_filter.lower() in c["name"].lower():
            marker = " <-- target"
        print(f"  {c['name']}: {c['count']} posts{marker}")

    # Step 2: Load existing posts to skip duplicates
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    existing = store.read()
    existing_ids = {p["id"] for p in existing}
    print(f"\nExisting posts in store: {len(existing_ids)}")

    # Step 3: Fetch saved posts from API
    col_str = f" in \"{collection_filter}\"" if collection_filter else ""
    limit_str = f" (limit: {limit})" if limit else ""
    print(f"\nFetching saved posts{col_str}{limit_str}...")

    api_posts = fetch_saved_posts(
        session=session,
        collection_map=collection_map,
        limit=limit,
        delay=delay,
        collection_filter=collection_filter,
    )

    if not api_posts:
        print("No posts fetched.")
        return

    # Step 4: Filter out duplicates
    new_posts = [p for p in api_posts if p["id"] not in existing_ids]
    skipped = len(api_posts) - len(new_posts)
    print(f"Fetched {len(api_posts)} posts ({len(new_posts)} new, {skipped} already in store)")

    if not new_posts:
        print("All posts already in store. Nothing to do.")
        return

    # Step 5: Download media for new posts
    if download_media and new_posts:
        print(f"\nDownloading media for {len(new_posts)} new posts...")
        executor = ThreadPoolExecutor(max_workers=4)
        futures = []
        media_downloaded = 0
        media_bytes = 0

        for post in new_posts:
            if post.get("media"):
                future = executor.submit(
                    download_post_media,
                    shortcode=post["id"],
                    username=post.get("author", {}).get("username", "unknown"),
                    media_list=[
                        {"url": m["url"], "type": m["media_type"],
                         "w": m.get("width", 0), "h": m.get("height", 0)}
                        for m in post["media"] if m.get("url")
                    ],
                )
                futures.append((future, post))

        for i, (future, post) in enumerate(futures):
            try:
                updated_media = future.result(timeout=120)
                post["media"] = [
                    {
                        "url": m.get("url", ""),
                        "media_type": m.get("type", "image"),
                        "local_path": m.get("local_path", ""),
                        "alt_text": "",
                        "width": m.get("w", 0),
                        "height": m.get("h", 0),
                    }
                    for m in updated_media
                ]
                for m in updated_media:
                    if m.get("local_path"):
                        lp = Path(m["local_path"])
                        if lp.exists():
                            media_downloaded += 1
                            media_bytes += lp.stat().st_size
            except Exception as e:
                logger.warning(f"Media download failed for {post['id']}: {e}")

            if (i + 1) % 50 == 0 or i == len(futures) - 1:
                mb = media_bytes / (1024 * 1024)
                print(f"  [{i+1}/{len(futures)}] {media_downloaded} files ({mb:.0f}MB)")

        executor.shutdown(wait=True)
        mb = media_bytes / (1024 * 1024)
        print(f"  Media: {media_downloaded} files ({mb:.1f} MB)")

    # Step 6: Append to store
    added = store.append(new_posts)
    print(f"\nAdded {added} new posts to store (total: {store.count()})")

    # Update sync tracker
    tracker = SyncTracker()
    cursor = tracker.get("instagram", "saved")
    cursor.mark_success(total_items=store.count())
    tracker.save(cursor)

    # Summary
    print(f"\n{'='*50}")
    print(f"Sync complete")
    print(f"  Fetched:  {len(api_posts)}")
    print(f"  New:      {len(new_posts)}")
    print(f"  Skipped:  {skipped} (already existed)")
    print(f"  Total:    {store.count()}")
    if download_media:
        print(f"  Media:    {media_downloaded} files")

    # Show collection breakdown of new posts
    from collections import Counter
    col_counter = Counter()
    for p in new_posts:
        for c in p.get("collections", []):
            col_counter[c] += 1
    if col_counter:
        print(f"\n  New posts by collection:")
        for name, count in col_counter.most_common(10):
            print(f"    {name}: {count}")


def show_collections():
    """List all saved collections from the API."""
    cookies = get_chrome_cookies()
    session = build_session(cookies)

    collections = fetch_collections(session)
    if not collections:
        print("No collections found.")
        return

    total = sum(c["count"] for c in collections)
    print(f"Found {len(collections)} collections ({total} total posts):\n")
    for c in sorted(collections, key=lambda x: x["count"], reverse=True):
        print(f"  {c['name']}: {c['count']} posts (id={c['id']})")


def show_stats():
    """Show sync status comparing API collections vs local store."""
    print("Loading Chrome cookies...")
    cookies = get_chrome_cookies()
    session = build_session(cookies)

    print("Fetching collections from API...")
    collections = fetch_collections(session)
    collection_map = {c["id"]: c["name"] for c in collections}

    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    posts = store.read()

    # Count local posts per collection
    from collections import Counter
    local_counter = Counter()
    for p in posts:
        for c in p.get("collections", []):
            local_counter[c] += 1

    print(f"\n{'Collection':<35} {'API':>6} {'Local':>6} {'Delta':>6}")
    print("-" * 60)

    api_total = 0
    local_total = 0
    for c in sorted(collections, key=lambda x: x["count"], reverse=True):
        name = c["name"]
        api_count = c["count"]
        local_count = local_counter.get(name, 0)
        delta = api_count - local_count
        api_total += api_count
        local_total += local_count
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"  {name:<33} {api_count:>6} {local_count:>6} {delta_str:>6}")

    print("-" * 60)
    total_delta = api_total - local_total
    delta_str = f"+{total_delta}" if total_delta > 0 else str(total_delta)
    print(f"  {'TOTAL':<33} {api_total:>6} {local_total:>6} {delta_str:>6}")
    print(f"\n  Local posts not in any collection: {len(posts) - local_total}")


def main():
    """CLI entry point."""
    import argparse

    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Bootstrap Instagram saved posts from API (no archive needed)"
    )
    sub = parser.add_subparsers(dest="command")

    sync_parser = sub.add_parser("sync", help="Sync saved posts from Instagram API")
    sync_parser.add_argument("--limit", type=int, default=None,
                             help="Max posts to fetch (default: all)")
    sync_parser.add_argument("--delay", type=float, default=2.0,
                             help="Seconds between page requests (default: 2.0)")
    sync_parser.add_argument("--no-media", action="store_true",
                             help="Skip media download")
    sync_parser.add_argument("--collection", type=str, default=None,
                             help="Only sync posts in this collection (substring match)")
    sync_parser.add_argument("--save-every", type=int, default=100,
                             help="Save progress every N posts (default: 100)")

    sub.add_parser("collections", help="List saved collections from API")
    sub.add_parser("stats", help="Compare API collections vs local store")

    args = parser.parse_args()

    if args.command == "sync":
        run_sync(
            limit=args.limit,
            delay=args.delay,
            download_media=not args.no_media,
            collection_filter=args.collection,
            save_every=args.save_every,
        )
    elif args.command == "collections":
        show_collections()
    elif args.command == "stats":
        show_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
