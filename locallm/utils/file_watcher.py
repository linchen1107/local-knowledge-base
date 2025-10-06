"""File watcher utilities for detecting document changes"""

import os
import time
from pathlib import Path
from typing import Dict, Set
import yaml


class DocumentWatcher:
    """Monitors document directory for changes"""

    def __init__(self, directory: str = "."):
        """Initialize the document watcher.

        Args:
            directory: Directory to watch
        """
        self.directory = Path(directory)
        self.supported_exts = {'.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'}
        self._last_snapshot = self._take_snapshot()
        self._last_check_time = time.time()

    def _take_snapshot(self) -> Dict[str, float]:
        """Take a snapshot of all documents and their modification times.

        Returns:
            Dictionary mapping file paths to modification times
        """
        snapshot = {}
        for file_path in self.directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_exts:
                try:
                    snapshot[str(file_path)] = file_path.stat().st_mtime
                except OSError:
                    # Skip files we can't access
                    pass
        return snapshot

    def check_for_changes(self) -> Dict[str, Set[str]]:
        """Check if any documents have changed since last check.

        Returns:
            Dictionary with 'added', 'modified', 'deleted' sets of file paths
        """
        current_snapshot = self._take_snapshot()

        # Find changes
        added = set(current_snapshot.keys()) - set(self._last_snapshot.keys())
        deleted = set(self._last_snapshot.keys()) - set(current_snapshot.keys())
        modified = set()

        for path in set(current_snapshot.keys()) & set(self._last_snapshot.keys()):
            if current_snapshot[path] != self._last_snapshot[path]:
                modified.add(path)

        # Update snapshot
        self._last_snapshot = current_snapshot
        self._last_check_time = time.time()

        return {
            'added': added,
            'modified': modified,
            'deleted': deleted
        }

    def has_changes(self) -> bool:
        """Quick check if there are any changes.

        Returns:
            True if any documents have changed
        """
        changes = self.check_for_changes()
        return bool(changes['added'] or changes['modified'] or changes['deleted'])

    def get_change_summary(self) -> str:
        """Get a human-readable summary of changes.

        Returns:
            Formatted string describing changes
        """
        changes = self.check_for_changes()

        if not (changes['added'] or changes['modified'] or changes['deleted']):
            return "No changes detected"

        summary = []

        if changes['added']:
            summary.append(f"Added: {len(changes['added'])} file(s)")
            for path in list(changes['added'])[:3]:  # Show max 3
                summary.append(f"  + {Path(path).name}")
            if len(changes['added']) > 3:
                summary.append(f"  ... and {len(changes['added']) - 3} more")

        if changes['modified']:
            summary.append(f"Modified: {len(changes['modified'])} file(s)")
            for path in list(changes['modified'])[:3]:
                summary.append(f"  ~ {Path(path).name}")
            if len(changes['modified']) > 3:
                summary.append(f"  ... and {len(changes['modified']) - 3} more")

        if changes['deleted']:
            summary.append(f"Deleted: {len(changes['deleted'])} file(s)")
            for path in list(changes['deleted'])[:3]:
                summary.append(f"  - {Path(path).name}")
            if len(changes['deleted']) > 3:
                summary.append(f"  ... and {len(changes['deleted']) - 3} more")

        return "\n".join(summary)

    def should_rebuild_map(self, threshold_minutes: int = 5) -> bool:
        """Check if enough time has passed and changes warrant rebuilding map.

        Args:
            threshold_minutes: Minimum minutes between checks

        Returns:
            True if map should be rebuilt
        """
        # Check time threshold
        minutes_since_check = (time.time() - self._last_check_time) / 60
        if minutes_since_check < threshold_minutes:
            return False

        # Check for changes
        return self.has_changes()
