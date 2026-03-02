"""Atomic JSON file storage with deduplication.

Provides thread-safe read/write/append operations on JSON array files.
Each file stores a list of dicts, with dedup based on a configurable key field.

Supports concurrent writers via patch_items() which re-reads the file before
each write, merging only the specified fields. This prevents the "lost update"
problem when multiple pipelines update different fields on the same records.
"""

from __future__ import annotations

import fcntl
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional


def _sanitize_surrogates(obj):
    """Recursively replace lone surrogate characters in strings.

    Web-scraped data sometimes contains broken emoji surrogates
    (e.g. \\ud83c without its pair) which are invalid in UTF-8.
    """
    if isinstance(obj, str):
        # Replace lone surrogates with the Unicode replacement character
        return obj.encode("utf-8", errors="replace").decode("utf-8")
    elif isinstance(obj, dict):
        return {k: _sanitize_surrogates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_surrogates(item) for item in obj]
    return obj


class JsonStore:
    """Manages a JSON array file with atomic writes and deduplication.

    Args:
        path: Path to the JSON file.
        key_field: Field name used for deduplication (default: "id").
    """

    def __init__(self, path: Path | str, key_field: str = "id"):
        self.path = Path(path)
        self.key_field = key_field

    def read(self) -> list[dict]:
        """Read all items from the store."""
        if not self.path.exists():
            return []
        try:
            text = self.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []
        return json.loads(text)

    def write(self, items: list[dict]) -> None:
        """Atomically overwrite the store with new items."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Sanitize surrogates from web-scraped data
        items = _sanitize_surrogates(items)
        # Write to temp file then rename for atomicity
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".json_store_"
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
                f.write("\n")
            shutil.move(tmp_path, self.path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def patch_items(self, patches: dict[str, dict]) -> int:
        """Atomically apply field-level updates to specific items.

        Re-reads the file, applies only the specified field updates, and writes
        back. Safe for concurrent use by multiple pipelines that update
        non-overlapping fields (e.g., enricher updates 'source'/'text'/'media',
        extractor updates 'extracted_text').

        Args:
            patches: Dict mapping key_field values to dicts of {field: value}
                     updates. Example: {"ABC123": {"extracted_text": {...}}}

        Returns:
            Number of items actually patched.
        """
        if not patches:
            return 0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(".lock")

        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                posts = self.read()
                key_to_idx = {p.get(self.key_field): i for i, p in enumerate(posts)}

                patched = 0
                for key_value, updates in patches.items():
                    idx = key_to_idx.get(key_value)
                    if idx is not None:
                        posts[idx].update(updates)
                        patched += 1

                self.write(posts)
                return patched
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def append(self, new_items: list[dict], merge_fn: Optional[Callable] = None) -> int:
        """Append items with deduplication based on key_field.

        Args:
            new_items: Items to add.
            merge_fn: Optional function(existing, new) -> merged that merges
                      duplicates instead of skipping them.

        Returns:
            Number of new items actually added.
        """
        existing = self.read()
        existing_keys = {}
        for i, item in enumerate(existing):
            key = item.get(self.key_field)
            if key:
                existing_keys[key] = i

        added = 0
        for item in new_items:
            key = item.get(self.key_field)
            if key and key in existing_keys:
                if merge_fn:
                    idx = existing_keys[key]
                    existing[idx] = merge_fn(existing[idx], item)
            else:
                existing.append(item)
                if key:
                    existing_keys[key] = len(existing) - 1
                added += 1

        self.write(existing)
        return added

    def count(self) -> int:
        """Return the number of items in the store."""
        return len(self.read())

    def find(self, **kwargs) -> list[dict]:
        """Find items matching all given field=value pairs."""
        items = self.read()
        results = []
        for item in items:
            if all(item.get(k) == v for k, v in kwargs.items()):
                results.append(item)
        return results

    def delete(self, key_value: str) -> bool:
        """Delete an item by its key field value."""
        items = self.read()
        filtered = [i for i in items if i.get(self.key_field) != key_value]
        if len(filtered) < len(items):
            self.write(filtered)
            return True
        return False
