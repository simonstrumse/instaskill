"""Sync state tracking per platform and content type."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SyncCursor:
    """Tracks sync progress for a specific platform + content_type combination.

    Used to enable incremental syncing - only fetch content newer than
    what we've already collected.
    """

    platform: str
    content_type: str
    last_id: str = ""
    last_timestamp: str = ""
    total_items: int = 0
    last_sync_at: str = ""
    last_sync_status: str = ""  # "success", "partial", "error"
    error_message: str = ""

    @property
    def key(self) -> str:
        return f"{self.platform}:{self.content_type}"

    def mark_success(self, total_items: int, last_id: str = "", last_timestamp: str = "") -> None:
        self.last_sync_at = datetime.now(timezone.utc).isoformat()
        self.last_sync_status = "success"
        self.total_items = total_items
        self.error_message = ""
        if last_id:
            self.last_id = last_id
        if last_timestamp:
            self.last_timestamp = last_timestamp

    def mark_error(self, error: str) -> None:
        self.last_sync_at = datetime.now(timezone.utc).isoformat()
        self.last_sync_status = "error"
        self.error_message = error

    def mark_partial(self, total_items: int, error: str = "") -> None:
        self.last_sync_at = datetime.now(timezone.utc).isoformat()
        self.last_sync_status = "partial"
        self.total_items = total_items
        self.error_message = error

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SyncCursor:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
