"""
Simple in-memory cache with Redis-like interface for compatibility.
"""

import time
from typing import Optional, Union


class SimpleCache:
    """A simple in-memory cache that mimics a subset of Redis commands."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._expiry: dict[str, float] = {}  # key -> expiry timestamp

    async def get(self, key: str) -> Optional[str]:
        """Get value by key. Returns None if key does not exist or expired."""
        # Check expiry
        if key in self._expiry:
            if self._expiry[key] < time.time():
                # Expired
                del self._data[key]
                del self._expiry[key]
                return None
            return self._data.get(key)
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Set key to value. If ex is given, set expiry in seconds."""
        self._data[key] = value
        if ex is not None:
            self._expiry[key] = time.time() + ex
        else:
            # Remove expiry if exists
            self._expiry.pop(key, None)

    async def delete(self, key: str) -> None:
        """Delete key."""
        self._data.pop(key, None)
        self._expiry.pop(key, None)

    async def incr(self, key: str) -> int:
        """Increment the integer value of key by 1. If key does not exist, set to 1."""
        if key not in self._data:
            self._data[key] = "0"
        try:
            val = int(self._data[key])
        except ValueError:
            val = 0
        val += 1
        self._data[key] = str(val)
        return val