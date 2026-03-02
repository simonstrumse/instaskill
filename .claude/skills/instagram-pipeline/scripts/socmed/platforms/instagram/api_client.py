"""Instagram API client using instagrapi.

Manages session persistence so you only need to log in once.
Subsequent runs reuse the saved session file.

Setup:
1. Run: python -m socmed creds setup instagram
2. Enter username, password, and 2FA code when prompted
3. Session is saved to credentials/instagram/session.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from socmed.config import PLATFORM_CREDENTIALS
from socmed.utils.retry import retry

logger = logging.getLogger(__name__)

_Client = None


def _get_client_class():
    global _Client
    if _Client is None:
        try:
            from instagrapi import Client
            _Client = Client
        except ImportError:
            raise ImportError(
                "instagrapi is required for Instagram integration. "
                "Install with: pip install instagrapi"
            )
    return _Client


class InstagramClient:
    """Wrapper around instagrapi with session persistence.

    Usage:
        client = InstagramClient()
        client.login("username", "password")  # First time
        # OR
        client.load_session()  # Subsequent runs
        saved = client.get_saved_posts()
    """

    def __init__(self):
        self._api = None
        self._session_path = PLATFORM_CREDENTIALS["instagram"]
        self._logged_in = False

    def _ensure_api(self):
        if self._api is None:
            Client = _get_client_class()
            self._api = Client()
            # Set reasonable defaults
            self._api.delay_range = [1, 3]

    def login(self, username: str, password: str, verification_code: str = "") -> bool:
        """Log in with username/password. Saves session on success."""
        self._ensure_api()
        try:
            if verification_code:
                self._api.login(username, password, verification_code=verification_code)
            else:
                self._api.login(username, password)
            self._save_session()
            self._logged_in = True
            logger.info(f"Logged in as {username}")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def load_session(self) -> bool:
        """Load a previously saved session."""
        if not self._session_path.exists():
            logger.error(f"No session file found at {self._session_path}")
            return False

        self._ensure_api()
        try:
            session_data = json.loads(self._session_path.read_text())
            self._api.set_settings(session_data)
            self._api.login_by_sessionid(session_data.get("authorization_data", {}).get("sessionid", ""))
            self._logged_in = True
            logger.info("Session loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

    def _save_session(self) -> None:
        """Save current session to file."""
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        settings = self._api.get_settings()
        self._session_path.write_text(json.dumps(settings, indent=2))
        logger.info(f"Session saved to {self._session_path}")

    def test_connection(self) -> bool:
        """Test if the current session is valid."""
        if not self._logged_in:
            if not self.load_session():
                return False
        try:
            info = self._api.account_info()
            logger.info(f"Connected as: {info.username}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    @property
    def api(self):
        """Direct access to the instagrapi Client for advanced operations."""
        if not self._logged_in:
            self.load_session()
        return self._api

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def get_saved_posts(self, amount: int = 50) -> list:
        """Fetch saved/bookmarked posts."""
        return self.api.collection_medias_by_name("All Posts", amount=amount)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def get_collections(self) -> list:
        """Fetch all saved collections."""
        return self.api.collections()

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def get_collection_medias(self, collection_id: str, amount: int = 50) -> list:
        """Fetch media from a specific collection."""
        return self.api.collection_medias(collection_id, amount=amount)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def get_direct_threads(self, amount: int = 20) -> list:
        """Fetch recent DM threads."""
        return self.api.direct_threads(amount=amount)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def get_direct_messages(self, thread_id: str, amount: int = 50) -> list:
        """Fetch messages from a specific DM thread."""
        return self.api.direct_messages(thread_id, amount=amount)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def send_direct_message(self, user_ids: list[int], text: str):
        """Send a DM to one or more users."""
        return self.api.direct_send(text, user_ids=user_ids)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def like_media(self, media_id: str) -> bool:
        """Like a post."""
        return self.api.media_like(media_id)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def comment_media(self, media_id: str, text: str):
        """Comment on a post."""
        return self.api.media_comment(media_id, text)

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def follow_user(self, user_id: str) -> bool:
        """Follow a user."""
        return self.api.user_follow(user_id)
