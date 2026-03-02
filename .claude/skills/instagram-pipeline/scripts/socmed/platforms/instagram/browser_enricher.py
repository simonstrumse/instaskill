"""Autonomous Instagram enrichment using Chrome's session cookies.

Reads Chrome's cookie database to get the authenticated sessionid,
then calls Instagram's web GraphQL API directly from Python. No browser
automation needed — just pure HTTP requests with the same cookies Chrome uses.

Designed to run continuously in the background with adaptive rate limiting.
Can be interrupted and resumed — only processes unenriched posts.

Usage:
    .venv/bin/python3 -m socmed.platforms.instagram.browser_enricher run
    .venv/bin/python3 -m socmed.platforms.instagram.browser_enricher run --limit 500
    .venv/bin/python3 -m socmed.platforms.instagram.browser_enricher run --no-media
    .venv/bin/python3 -m socmed.platforms.instagram.browser_enricher download-media
    .venv/bin/python3 -m socmed.platforms.instagram.browser_enricher stats
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from socmed.config import DATA_FILES, MEDIA_DIR
from socmed.storage.json_store import JsonStore
from socmed.storage.sync_tracker import SyncTracker

logger = logging.getLogger(__name__)

# Instagram web GraphQL endpoint and doc_id for PolarisPostRootQuery
GRAPHQL_URL = "https://www.instagram.com/graphql/query"
GRAPHQL_DOC_ID = "34052121741099006"
IG_APP_ID = "936619743392459"

# REST API endpoint (fallback when GraphQL is checkpointed)
REST_MEDIA_URL = "https://www.instagram.com/api/v1/media/{pk}/info/"

# Base64 alphabet used by Instagram for shortcode <-> PK conversion
_IG_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def get_chrome_cookies() -> dict[str, str]:
    """Extract Instagram cookies from Chrome's cookie database.

    Uses browser_cookie3 to read Chrome's encrypted cookie store,
    which can access HttpOnly cookies like sessionid that JavaScript cannot.
    """
    import browser_cookie3

    cj = browser_cookie3.chrome(domain_name=".instagram.com")
    cookies = {}
    for cookie in cj:
        if "instagram" in cookie.domain:
            cookies[cookie.name] = cookie.value

    required = ["sessionid", "csrftoken", "ds_user_id"]
    missing = [k for k in required if k not in cookies]
    if missing:
        raise RuntimeError(
            f"Missing Instagram cookies: {missing}. "
            "Make sure you're logged into Instagram in Chrome."
        )

    return cookies


def build_session(cookies: dict[str, str]) -> requests.Session:
    """Build a requests session with Instagram's expected headers and cookies."""
    session = requests.Session()

    # Set cookies
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".instagram.com")

    # Set headers to match Instagram's web app
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "X-IG-App-ID": IG_APP_ID,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.instagram.com/",
        "Origin": "https://www.instagram.com",
    })

    return session


def shortcode_to_pk(shortcode: str) -> int:
    """Convert an Instagram shortcode to its numeric media PK.

    Instagram shortcodes are base64-encoded (custom alphabet) representations
    of the numeric media primary key. Decoding is a simple base-64 accumulation.
    """
    pk = 0
    for char in shortcode:
        pk = pk * 64 + _IG_ALPHABET.index(char)
    return pk


def _extract_media_from_item(item: dict) -> list[dict]:
    """Extract media list from an Instagram API item (shared by GraphQL and REST)."""
    media = []
    img_versions = (item.get("image_versions2") or {}).get("candidates")
    if img_versions:
        img = img_versions[0]
        media.append({"type": "image", "url": img.get("url", ""),
                      "w": img.get("width", 0), "h": img.get("height", 0)})
    if item.get("video_versions"):
        vid = item["video_versions"][0]
        media.append({"type": "video", "url": vid.get("url", ""),
                      "w": vid.get("width", 0), "h": vid.get("height", 0)})
    if item.get("carousel_media"):
        for cm in item["carousel_media"]:
            cm_img = (cm.get("image_versions2") or {}).get("candidates")
            if cm_img:
                img = cm_img[0]
                media.append({"type": "image", "url": img.get("url", ""),
                              "w": img.get("width", 0), "h": img.get("height", 0)})
            if cm.get("video_versions"):
                vid = cm["video_versions"][0]
                media.append({"type": "video", "url": vid.get("url", ""),
                              "w": vid.get("width", 0), "h": vid.get("height", 0)})
    return media


def _item_to_result(shortcode: str, item: dict) -> dict:
    """Convert an Instagram API item to our standard result format."""
    caption_text = ""
    if item.get("caption") and item["caption"].get("text"):
        caption_text = item["caption"]["text"]

    user = item.get("user", {})

    return {
        "shortcode": shortcode,
        "status": "ok",
        "pk": str(item.get("pk", "")),
        "username": user.get("username", ""),
        "full_name": user.get("full_name", ""),
        "caption": caption_text,
        "like_count": item.get("like_count", 0),
        "comment_count": item.get("comment_count", 0),
        "taken_at": item.get("taken_at", 0),
        "media_type": item.get("media_type", 0),
        "media": _extract_media_from_item(item),
    }


def fetch_post_rest(session: requests.Session, shortcode: str) -> dict:
    """Fetch a post via Instagram's REST API (v1/media/{pk}/info/).

    This is the fallback when GraphQL is checkpointed. Converts the shortcode
    to a numeric PK, then hits the REST endpoint which uses a different
    rate-limiting path than GraphQL.
    """
    try:
        pk = shortcode_to_pk(shortcode)
    except (ValueError, IndexError):
        return {"shortcode": shortcode, "status": "error", "message": "invalid shortcode"}

    url = REST_MEDIA_URL.format(pk=pk)

    try:
        resp = session.get(url, timeout=15)
    except requests.RequestException as e:
        return {"shortcode": shortcode, "status": "error", "message": str(e)}

    if resp.status_code == 404:
        return {"shortcode": shortcode, "status": "not_found"}

    if resp.status_code == 429:
        return {"shortcode": shortcode, "status": "rate_limited"}

    if resp.status_code != 200:
        return {"shortcode": shortcode, "status": "error", "code": resp.status_code}

    try:
        data = resp.json()
    except ValueError:
        return {"shortcode": shortcode, "status": "error", "message": "invalid json"}

    items = data.get("items")
    if not items:
        return {"shortcode": shortcode, "status": "not_found"}

    return _item_to_result(shortcode, items[0])


def _fetch_post_graphql(session: requests.Session, shortcode: str) -> dict:
    """Fetch a post via Instagram's GraphQL API (primary method)."""
    payload = {
        "doc_id": GRAPHQL_DOC_ID,
        "variables": json.dumps({"shortcode": shortcode}),
    }

    try:
        resp = session.post(
            GRAPHQL_URL,
            data=payload,
            timeout=15,
        )
    except requests.RequestException as e:
        return {"shortcode": shortcode, "status": "error", "message": str(e)}

    if resp.status_code == 429:
        return {"shortcode": shortcode, "status": "rate_limited"}

    if resp.status_code != 200:
        return {"shortcode": shortcode, "status": "error", "code": resp.status_code}

    try:
        data = resp.json()
    except ValueError:
        return {"shortcode": shortcode, "status": "error", "message": "invalid json"}

    info = (data.get("data") or {}).get("xdt_api__v1__media__shortcode__web_info")
    if not info or not info.get("items"):
        if data.get("errors"):
            return {"shortcode": shortcode, "status": "error",
                    "message": data["errors"][0].get("message", "unknown")}
        return {"shortcode": shortcode, "status": "not_found"}

    return _item_to_result(shortcode, info["items"][0])


# Module-level flag: switches to REST-only after GraphQL checkpoint detected.
# This avoids wasting a request on every post once we know GraphQL is down.
_graphql_available = True


def fetch_post_by_shortcode(session: requests.Session, shortcode: str) -> dict:
    """Fetch a single post's data, trying GraphQL first then REST fallback.

    If GraphQL returns a checkpoint (invalid json / HTML), automatically
    switches to REST-only mode for the remainder of the session.

    Returns a dict with status and post data, matching the format
    used by apply_results().
    """
    global _graphql_available

    if _graphql_available:
        result = _fetch_post_graphql(session, shortcode)
        if result["status"] != "error" or result.get("message") != "invalid json":
            return result

        # GraphQL returned HTML (checkpoint) — switch to REST-only
        logger.info("GraphQL checkpointed, switching to REST API")
        _graphql_available = False

    return fetch_post_rest(session, shortcode)


def _url_hash(url: str) -> str:
    """Short hash of a URL for unique filenames."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _guess_ext(url: str, media_type: str) -> str:
    """Guess file extension from URL path or media type."""
    path = urlparse(url).path.split("?")[0]
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".webm"):
        return ext
    return ".mp4" if media_type == "video" else ".jpg"


def download_post_media(
    shortcode: str,
    username: str,
    media_list: list[dict],
    base_dir: Path | None = None,
) -> list[dict]:
    """Download all media items for a single post.

    Downloads each media URL to data/media/instagram/{username}/{shortcode}_{hash}.{ext}.
    Returns updated media_list with local_path set for each successful download.
    Uses a plain requests.get() — CDN URLs don't need Instagram auth cookies.
    """
    base = base_dir or (MEDIA_DIR / "instagram")
    safe_user = "".join(c for c in username if c.isalnum() or c in "._-") or "unknown"
    target_dir = base / safe_user
    target_dir.mkdir(parents=True, exist_ok=True)

    updated = []
    for m in media_list:
        url = m.get("url", "")
        if not url:
            updated.append(m)
            continue

        ext = _guess_ext(url, m.get("type", "image"))
        filename = f"{shortcode}_{_url_hash(url)}{ext}"
        filepath = target_dir / filename

        # Skip if already downloaded
        if filepath.exists() and filepath.stat().st_size > 0:
            updated.append({**m, "local_path": str(filepath)})
            continue

        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            updated.append({**m, "local_path": str(filepath)})
        except Exception as e:
            logger.warning(f"Failed to download media for {shortcode}: {e}")
            updated.append(m)

    return updated


def get_pending_shortcodes(
    limit: int | None = None,
    collection: str | None = None,
) -> list[str]:
    """Get shortcodes of posts that need enrichment.

    Args:
        limit: Max shortcodes to return.
        collection: Only include posts in this collection (substring match).
    """
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    posts = store.read()
    pending = []
    for post in posts:
        if post.get("source") == "archive" and not post.get("text"):
            if collection:
                post_cols = post.get("collections", [])
                if not any(collection.lower() in c.lower() for c in post_cols):
                    continue
            pending.append(post["id"])
            if limit and len(pending) >= limit:
                break
    return pending


def apply_results(results: list[dict]) -> dict:
    """Apply fetched results to the data store using patch_items.

    Uses merge-on-write to avoid clobbering extraction data written by
    the media_extractor pipeline running concurrently.

    Returns dict with counts: enriched, deleted, failed, remaining.
    """
    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])

    enriched = 0
    deleted = 0
    failed = 0
    patches: dict[str, dict] = {}

    for result in results:
        sc = result["shortcode"]

        if result["status"] == "ok":
            patch = {
                "text": result.get("caption") or "[No caption]",
                "author": {
                    "username": result.get("username", ""),
                    "display_name": result.get("full_name", ""),
                    "profile_url": f"https://www.instagram.com/{result.get('username', '')}/",
                },
                "source": "archive+api",
            }

            if result.get("media"):
                patch["media"] = [
                    {
                        "url": m.get("url", ""),
                        "media_type": m.get("type", "image"),
                        "local_path": m.get("local_path", ""),
                        "alt_text": "",
                        "width": m.get("w", 0),
                        "height": m.get("h", 0),
                    }
                    for m in result["media"]
                ]

            if result.get("like_count"):
                patch["like_count"] = result["like_count"]
            if result.get("comment_count"):
                patch["reply_count"] = result["comment_count"]

            if result.get("taken_at"):
                patch["created_at"] = datetime.fromtimestamp(
                    result["taken_at"], tz=timezone.utc
                ).isoformat()

            if result.get("pk"):
                patch["media_pk"] = result["pk"]

            patches[sc] = patch
            enriched += 1

        elif result["status"] == "not_found":
            patches[sc] = {
                "source": "archive:deleted",
                "text": "[Post no longer available]",
            }
            deleted += 1

        else:
            failed += 1

    store.patch_items(patches)

    # Read fresh to count remaining
    posts = store.read()
    remaining = sum(
        1 for p in posts
        if p.get("source") == "archive" and not p.get("text")
    )

    tracker = SyncTracker()
    cursor = tracker.get("instagram", "enrichment")
    cursor.mark_success(total_items=enriched)
    tracker.save(cursor)

    return {
        "enriched": enriched,
        "deleted": deleted,
        "failed": failed,
        "remaining": remaining,
    }


def run_enrichment(
    limit: int | None = None,
    delay: float = 3.0,
    save_every: int = 25,
    download_media: bool = True,
    collection: str | None = None,
):
    """Run the full enrichment pipeline autonomously.

    Args:
        limit: Max posts to process (None = all pending).
        delay: Seconds between requests (default 3.0 for safety).
        save_every: Save progress every N posts.
        download_media: Download media files inline (default True).
    """
    print("Loading Chrome cookies...")
    cookies = get_chrome_cookies()
    session = build_session(cookies)
    print(f"Authenticated as user {cookies.get('ds_user_id', '?')}")

    # Quick auth test — tries GraphQL first, falls back to REST
    global _graphql_available
    _graphql_available = True  # Reset for fresh session
    test = fetch_post_by_shortcode(session, "DUGZG3CjcN-")  # known test shortcode
    if test["status"] == "error":
        print(f"Auth test failed: {test}")
        print("Make sure you're logged into Instagram in Chrome.")
        sys.exit(1)
    api_mode = "GraphQL" if _graphql_available else "REST API (GraphQL checkpointed)"
    print(f"Auth test passed via {api_mode} (fetched @{test.get('username', '?')})")

    pending = get_pending_shortcodes(limit=limit, collection=collection)
    total_pending = len(pending)
    if not pending:
        print("No posts need enrichment.")
        return

    media_mode = "with media download" if download_media else "metadata only"
    col_str = f" in \"{collection}\"" if collection else ""
    print(f"\nStarting enrichment: {total_pending} posts{col_str} ({media_mode})")
    print(f"Rate: 1 request every {delay}s (~{60/delay:.0f}/min)")
    eta_min = total_pending * delay / 60
    print(f"Estimated time: ~{eta_min:.0f} min ({eta_min/60:.1f} hrs)")
    print()

    results_batch = []
    enriched_total = 0
    failed_total = 0
    deleted_total = 0
    media_downloaded = 0
    media_failed = 0
    media_bytes = 0
    rate_limited = False
    consecutive_failures = 0

    # Instagram's anti-automation kicks in after ~700 requests in a session.
    # Proactive cooldown every 600 posts prevents hitting the wall.
    COOLDOWN_EVERY = 600
    COOLDOWN_SECS = 120  # 2 minutes
    # Also trigger early cooldown if we see many consecutive failures.
    MAX_CONSECUTIVE_FAILURES = 10

    # Thread pool for concurrent media downloads — CDN requests don't count
    # against the GraphQL rate limit, so downloads run during API sleep time.
    executor = ThreadPoolExecutor(max_workers=4) if download_media else None
    # Maps: future -> index in results_batch
    pending_futures: list[tuple] = []

    start_time = time.time()

    for i, shortcode in enumerate(pending):
        result = fetch_post_by_shortcode(session, shortcode)
        results_batch.append(result)

        # Submit media downloads to thread pool (non-blocking)
        if download_media and result["status"] == "ok" and result.get("media"):
            future = executor.submit(
                download_post_media,
                shortcode=shortcode,
                username=result.get("username", "unknown"),
                media_list=result["media"],
            )
            pending_futures.append((future, len(results_batch) - 1))

        status_char = "." if result["status"] == "ok" else \
                      "X" if result["status"] == "not_found" else \
                      "!" if result["status"] == "rate_limited" else "?"

        # Track counts
        if result["status"] == "ok":
            enriched_total += 1
            consecutive_failures = 0
        elif result["status"] == "not_found":
            deleted_total += 1
            consecutive_failures = 0
        elif result["status"] == "rate_limited":
            rate_limited = True
            consecutive_failures += 1
        else:
            failed_total += 1
            consecutive_failures += 1

        # Progress output (compact line, no newline until save)
        sys.stdout.write(status_char)
        sys.stdout.flush()

        # Proactive cooldown every COOLDOWN_EVERY posts to avoid anti-automation
        needs_cooldown = (
            (i + 1) % COOLDOWN_EVERY == 0
            or consecutive_failures >= MAX_CONSECUTIVE_FAILURES
        )

        # Periodic save
        if (i + 1) % save_every == 0 or i == len(pending) - 1 or rate_limited or needs_cooldown:
            # Collect all pending media downloads before saving
            for future, batch_idx in pending_futures:
                try:
                    updated_media = future.result(timeout=120)
                    results_batch[batch_idx]["media"] = updated_media
                    for m in updated_media:
                        if m.get("local_path"):
                            lp = Path(m["local_path"])
                            if lp.exists():
                                media_downloaded += 1
                                media_bytes += lp.stat().st_size
                        elif m.get("url"):
                            media_failed += 1
                except Exception as e:
                    logger.warning(f"Media download failed: {e}")
            pending_futures.clear()

            counts = apply_results(results_batch)
            results_batch = []

            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            remaining = counts["remaining"]

            media_mb = media_bytes / (1024 * 1024)
            media_str = f" | {media_downloaded} media ({media_mb:.0f}MB)" if download_media else ""
            print(f" [{i+1}/{total_pending}] "
                  f"+{counts['enriched']} enriched, "
                  f"{counts['deleted']} deleted, "
                  f"{counts['failed']} failed | "
                  f"{remaining} remaining | "
                  f"{rate:.0f}/min{media_str}")

        if rate_limited:
            print("\nRate limited! Backing off for 60 seconds...")
            time.sleep(60)
            # Refresh cookies in case session rotated
            try:
                cookies = get_chrome_cookies()
                session = build_session(cookies)
                rate_limited = False
                consecutive_failures = 0
                print("Resumed after rate limit pause.")
            except Exception as e:
                print(f"Failed to refresh cookies: {e}")
                break

        elif needs_cooldown:
            reason = (f"{consecutive_failures} consecutive failures"
                      if consecutive_failures >= MAX_CONSECUTIVE_FAILURES
                      else f"proactive cooldown at {i+1} posts")
            print(f"\nCooling down ({reason}): pausing {COOLDOWN_SECS}s...")
            time.sleep(COOLDOWN_SECS)
            # Refresh cookies after cooldown
            try:
                cookies = get_chrome_cookies()
                session = build_session(cookies)
                consecutive_failures = 0
                print("Resumed after cooldown.")
            except Exception as e:
                print(f"Failed to refresh cookies: {e}")
                break

        elif i < len(pending) - 1:
            time.sleep(delay)

    if executor:
        executor.shutdown(wait=True)

    # Final summary
    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"Enrichment complete in {elapsed/60:.1f} minutes")
    print(f"  Enriched: {enriched_total}")
    print(f"  Deleted:  {deleted_total}")
    print(f"  Failed:   {failed_total}")
    if download_media:
        media_mb = media_bytes / (1024 * 1024)
        print(f"  Media:    {media_downloaded} files ({media_mb:.1f} MB)")
        if media_failed:
            print(f"  Media failed: {media_failed}")

    remaining = sum(
        1 for p in JsonStore(DATA_FILES["instagram"]["saved_posts"]).read()
        if p.get("source") == "archive" and not p.get("text")
    )
    print(f"  Remaining: {remaining}")


def run_media_download(limit: int | None = None):
    """Download media for already-enriched posts that are missing local files.

    Re-fetches GraphQL data for fresh CDN URLs since saved URLs expire.
    Only processes posts with source='archive+api' that have media without local_path.
    """
    print("Loading Chrome cookies...")
    cookies = get_chrome_cookies()
    session = build_session(cookies)
    print(f"Authenticated as user {cookies.get('ds_user_id', '?')}")

    store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
    posts = store.read()

    # Find enriched posts missing media downloads
    needs_media = []
    for post in posts:
        if post.get("source") != "archive+api":
            continue
        for m in post.get("media", []):
            if m.get("url") and not m.get("local_path"):
                needs_media.append(post)
                break

    if limit:
        needs_media = needs_media[:limit]

    if not needs_media:
        print("No posts need media downloads.")
        return

    print(f"\nDownloading media for {len(needs_media)} enriched posts...")
    print("(Re-fetching GraphQL for fresh CDN URLs)\n")

    downloaded_total = 0
    failed_total = 0
    bytes_total = 0

    sc_to_idx = {p["id"]: i for i, p in enumerate(posts)}

    for i, post in enumerate(needs_media):
        shortcode = post["id"]
        result = fetch_post_by_shortcode(session, shortcode)

        if result["status"] != "ok" or not result.get("media"):
            sys.stdout.write("?")
            sys.stdout.flush()
            failed_total += 1
            time.sleep(2.5)
            continue

        updated_media = download_post_media(
            shortcode=shortcode,
            username=result.get("username", post.get("author", {}).get("username", "unknown")),
            media_list=result["media"],
        )

        # Update the post's media with local paths
        idx = sc_to_idx.get(shortcode)
        if idx is not None:
            posts[idx]["media"] = [
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
                    downloaded_total += 1
                    bytes_total += lp.stat().st_size

        sys.stdout.write(".")
        sys.stdout.flush()

        # Save every 25 posts
        if (i + 1) % 25 == 0 or i == len(needs_media) - 1:
            store.write(posts)
            mb = bytes_total / (1024 * 1024)
            print(f" [{i+1}/{len(needs_media)}] {downloaded_total} files ({mb:.0f}MB)")

        time.sleep(2.5)

    store.write(posts)
    mb = bytes_total / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"Media download complete")
    print(f"  Downloaded: {downloaded_total} files ({mb:.1f} MB)")
    if failed_total:
        print(f"  Failed: {failed_total}")


def main():
    """CLI entry point."""
    import argparse

    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Instagram enrichment via Chrome session cookies"
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run enrichment with media download")
    run_parser.add_argument("--limit", type=int, default=None,
                            help="Max posts to process (default: all)")
    run_parser.add_argument("--delay", type=float, default=3.0,
                            help="Seconds between requests (default: 3.0)")
    run_parser.add_argument("--save-every", type=int, default=25,
                            help="Save progress every N posts (default: 25)")
    run_parser.add_argument("--no-media", action="store_true",
                            help="Skip media download (metadata only)")
    run_parser.add_argument("--collection", type=str, default=None,
                            help="Only enrich posts in this collection (substring match)")

    dm_parser = sub.add_parser("download-media",
                               help="Download media for already-enriched posts")
    dm_parser.add_argument("--limit", type=int, default=None,
                           help="Max posts to process (default: all)")

    sub.add_parser("stats", help="Show enrichment statistics")
    sub.add_parser("test", help="Test authentication and media download")

    args = parser.parse_args()

    if args.command == "run":
        run_enrichment(
            limit=args.limit,
            delay=args.delay,
            save_every=args.save_every,
            download_media=not args.no_media,
            collection=args.collection,
        )

    elif args.command == "download-media":
        run_media_download(limit=args.limit)

    elif args.command == "stats":
        from socmed.platforms.instagram.enricher import get_enrichment_stats
        stats = get_enrichment_stats()
        print(f"Total:     {stats['total']}")
        print(f"Enriched:  {stats['enriched']}")
        print(f"Pending:   {stats['pending']}")
        print(f"Deleted:   {stats['deleted']}")
        if stats["pending"]:
            eta = stats["pending"] * 3 / 60
            print(f"Est. time: ~{eta:.0f} min ({eta/60:.1f} hrs) at 20/min")

        # Media stats
        media_dir = MEDIA_DIR / "instagram"
        if media_dir.exists():
            files = list(media_dir.rglob("*"))
            media_files = [f for f in files if f.is_file() and f.suffix in (
                ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".webm")]
            total_bytes = sum(f.stat().st_size for f in media_files)
            mb = total_bytes / (1024 * 1024)
            print(f"\nMedia:     {len(media_files)} files ({mb:.1f} MB)")

            # Count posts with vs without local media
            store = JsonStore(DATA_FILES["instagram"]["saved_posts"])
            posts = store.read()
            with_media = sum(1 for p in posts if any(
                m.get("local_path") for m in p.get("media", [])))
            without_media = sum(1 for p in posts if p.get("source") == "archive+api"
                              and p.get("media") and not any(
                                  m.get("local_path") for m in p["media"]))
            print(f"  With local files:    {with_media}")
            print(f"  Missing local files: {without_media}")

    elif args.command == "test":
        print("Loading Chrome cookies...")
        cookies = get_chrome_cookies()
        print(f"Found cookies: {list(cookies.keys())}")
        session = build_session(cookies)

        # Test both APIs
        print("\n--- GraphQL API ---")
        gql_result = _fetch_post_graphql(session, "DUGZG3CjcN-")
        if gql_result["status"] == "ok":
            print(f"  GraphQL: OK (@{gql_result['username']})")
        else:
            print(f"  GraphQL: {gql_result.get('message', gql_result['status'])}")

        print("\n--- REST API ---")
        rest_result = fetch_post_rest(session, "DUGZG3CjcN-")
        if rest_result["status"] == "ok":
            print(f"  REST: OK (@{rest_result['username']})")
        else:
            print(f"  REST: {rest_result.get('message', rest_result['status'])}")

        # Use whichever worked
        result = gql_result if gql_result["status"] == "ok" else rest_result
        if result["status"] == "ok":
            print(f"\nPost by @{result['username']}")
            print(f"  Caption: {result['caption'][:80]}...")
            print(f"  Likes: {result['like_count']}, Comments: {result['comment_count']}")
            print(f"  Media items: {len(result.get('media', []))}")

            # Test media download
            if result.get("media"):
                print("\nTesting media download...")
                updated = download_post_media(
                    shortcode="DUGZG3CjcN-",
                    username=result["username"],
                    media_list=result["media"],
                )
                for m in updated:
                    if m.get("local_path"):
                        size = Path(m["local_path"]).stat().st_size
                        print(f"  Downloaded: {Path(m['local_path']).name} ({size:,} bytes)")
                    else:
                        print(f"  Failed: {m.get('type', '?')} media")
        else:
            print(f"\nBoth APIs failed: {result}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
