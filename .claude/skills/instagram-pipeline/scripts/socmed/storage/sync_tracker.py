"""Sync state management across platforms and content types."""

from __future__ import annotations

from pathlib import Path

from socmed.config import SYNC_STATE_FILE
from socmed.models.sync_state import SyncCursor
from socmed.storage.json_store import JsonStore


class SyncTracker:
    """Manages sync cursors for all platform + content_type combinations.

    The sync state file stores an array of SyncCursor dicts, keyed
    by "platform:content_type".
    """

    def __init__(self, path: Path | str | None = None):
        self.store = JsonStore(path or SYNC_STATE_FILE, key_field="key")

    def get(self, platform: str, content_type: str) -> SyncCursor:
        """Get the sync cursor for a platform+content_type. Creates if missing."""
        key = f"{platform}:{content_type}"
        items = self.store.find(key=key)
        if items:
            return SyncCursor.from_dict(items[0])
        return SyncCursor(platform=platform, content_type=content_type)

    def save(self, cursor: SyncCursor) -> None:
        """Save a sync cursor, creating or updating as needed."""
        items = self.store.read()
        key = cursor.key
        found = False
        for i, item in enumerate(items):
            if item.get("key") == key:
                items[i] = {**cursor.to_dict(), "key": key}
                found = True
                break
        if not found:
            items.append({**cursor.to_dict(), "key": key})
        self.store.write(items)

    def get_all(self) -> list[SyncCursor]:
        """Get all sync cursors."""
        return [SyncCursor.from_dict(item) for item in self.store.read()]

    def summary(self) -> str:
        """Return a human-readable sync status summary."""
        cursors = self.get_all()
        if not cursors:
            return "No sync history found."

        lines = ["Platform         | Content  | Items | Last Sync            | Status"]
        lines.append("-" * 75)
        for c in sorted(cursors, key=lambda x: x.key):
            last_sync = c.last_sync_at[:19] if c.last_sync_at else "never"
            lines.append(
                f"{c.platform:<16} | {c.content_type:<8} | {c.total_items:>5} | {last_sync:<20} | {c.last_sync_status}"
            )
        return "\n".join(lines)
