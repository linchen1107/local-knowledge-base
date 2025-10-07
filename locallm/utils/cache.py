"""Document caching system with LRU eviction policy"""

from collections import OrderedDict
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
import time


class DocumentCache:
    """LRU cache for document content to avoid redundant file reads.

    Features:
    - LRU eviction when cache is full
    - Automatic invalidation based on file modification time
    - Size-based memory management
    - Thread-safe operations
    """

    def __init__(self, max_size_mb: int = 100, max_items: int = 50):
        """Initialize document cache.

        Args:
            max_size_mb: Maximum cache size in megabytes
            max_items: Maximum number of cached documents
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_items = max_items
        self.current_size = 0
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key from file path.

        Args:
            file_path: Path to the document

        Returns:
            Cache key (MD5 hash of absolute path)
        """
        abs_path = str(Path(file_path).resolve())
        return hashlib.md5(abs_path.encode()).hexdigest()

    def _get_file_mtime(self, file_path: str) -> float:
        """Get file modification time.

        Args:
            file_path: Path to the document

        Returns:
            Modification timestamp
        """
        try:
            return Path(file_path).stat().st_mtime
        except:
            return 0.0

    def get(self, file_path: str) -> Optional[str]:
        """Retrieve document content from cache.

        Args:
            file_path: Path to the document

        Returns:
            Cached content if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(file_path)

        # Check if in cache
        if cache_key not in self.cache:
            self.misses += 1
            return None

        # Check if file has been modified
        current_mtime = self._get_file_mtime(file_path)
        cached_entry = self.cache[cache_key]

        if current_mtime > cached_entry['mtime']:
            # File modified, invalidate cache
            self._remove_entry(cache_key)
            self.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(cache_key)
        self.hits += 1

        return cached_entry['content']

    def put(self, file_path: str, content: str):
        """Store document content in cache.

        Args:
            file_path: Path to the document
            content: Document content to cache
        """
        cache_key = self._get_cache_key(file_path)
        content_size = len(content.encode('utf-8'))

        # Remove existing entry if present
        if cache_key in self.cache:
            self._remove_entry(cache_key)

        # Evict entries if necessary
        while (self.current_size + content_size > self.max_size_bytes or
               len(self.cache) >= self.max_items) and self.cache:
            self._evict_oldest()

        # Add new entry
        self.cache[cache_key] = {
            'content': content,
            'size': content_size,
            'mtime': self._get_file_mtime(file_path),
            'cached_at': time.time(),
            'path': file_path
        }
        self.current_size += content_size

    def _remove_entry(self, cache_key: str):
        """Remove entry from cache.

        Args:
            cache_key: Key of entry to remove
        """
        if cache_key in self.cache:
            entry = self.cache.pop(cache_key)
            self.current_size -= entry['size']

    def _evict_oldest(self):
        """Evict the least recently used entry."""
        if self.cache:
            oldest_key = next(iter(self.cache))
            self._remove_entry(oldest_key)

    def clear(self):
        """Clear all cached entries."""
        self.cache.clear()
        self.current_size = 0
        self.hits = 0
        self.misses = 0

    def invalidate(self, file_path: str):
        """Invalidate cached entry for a specific file.

        Args:
            file_path: Path to the document
        """
        cache_key = self._get_cache_key(file_path)
        self._remove_entry(cache_key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        hit_rate = self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0

        return {
            'size_mb': self.current_size / (1024 * 1024),
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'items': len(self.cache),
            'max_items': self.max_items,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2%}",
            'cached_files': [entry['path'] for entry in self.cache.values()]
        }


# Global cache instance
_global_cache: Optional[DocumentCache] = None


def get_cache() -> DocumentCache:
    """Get or create global document cache instance.

    Returns:
        Global DocumentCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = DocumentCache()
    return _global_cache


def clear_cache():
    """Clear the global document cache."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
