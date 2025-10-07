"""File locking mechanism to prevent concurrent modifications"""

import os
import time
from pathlib import Path
from typing import Optional
import errno

# Platform-specific imports
if os.name != 'nt':
    import fcntl


class FileLock:
    """Cross-platform file lock for preventing concurrent access.

    Uses fcntl on Unix/Linux and msvcrt on Windows.
    """

    def __init__(self, lock_file: str, timeout: float = 10.0):
        """Initialize file lock.

        Args:
            lock_file: Path to the lock file
            timeout: Maximum time to wait for lock (seconds)
        """
        self.lock_file = Path(lock_file)
        self.lock_file_fd: Optional[int] = None
        self.timeout = timeout
        self.is_locked = False

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire the lock.

        Args:
            blocking: If True, wait until lock is available

        Returns:
            True if lock acquired, False otherwise
        """
        # Ensure lock file directory exists
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()

        while True:
            try:
                # Open lock file (create if doesn't exist)
                self.lock_file_fd = os.open(
                    str(self.lock_file),
                    os.O_RDWR | os.O_CREAT | os.O_TRUNC
                )

                # Try to acquire exclusive lock
                if os.name == 'nt':
                    # Windows
                    import msvcrt
                    msvcrt.locking(self.lock_file_fd, msvcrt.LK_NBLCK, 1)
                else:
                    # Unix/Linux
                    fcntl.flock(self.lock_file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Write PID to lock file
                os.write(self.lock_file_fd, str(os.getpid()).encode())
                os.fsync(self.lock_file_fd)

                self.is_locked = True
                return True

            except (IOError, OSError) as e:
                # Lock is held by another process
                if self.lock_file_fd is not None:
                    try:
                        os.close(self.lock_file_fd)
                    except:
                        pass
                    self.lock_file_fd = None

                if not blocking:
                    return False

                # Check timeout
                if time.time() - start_time >= self.timeout:
                    return False

                # Wait before retry
                time.sleep(0.1)

    def release(self):
        """Release the lock."""
        if not self.is_locked:
            return

        try:
            if self.lock_file_fd is not None:
                # Release the lock
                if os.name == 'nt':
                    import msvcrt
                    try:
                        # On Windows, unlocking may fail if already unlocked
                        msvcrt.locking(self.lock_file_fd, msvcrt.LK_UNLCK, 1)
                    except (OSError, IOError):
                        pass  # Already unlocked, ignore
                else:
                    fcntl.flock(self.lock_file_fd, fcntl.LOCK_UN)

                # Close the file descriptor
                try:
                    os.close(self.lock_file_fd)
                except:
                    pass
                self.lock_file_fd = None

            # On Windows, give OS time to release file handle
            if os.name == 'nt':
                time.sleep(0.05)

            # Remove lock file (multiple attempts for Windows)
            if self.lock_file.exists():
                for attempt in range(3):
                    try:
                        self.lock_file.unlink()
                        break
                    except (OSError, PermissionError):
                        if attempt < 2:
                            time.sleep(0.1)
                        else:
                            pass  # Best effort, give up after 3 attempts

            self.is_locked = False

        except Exception as e:
            # Best effort cleanup
            pass

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock on {self.lock_file} within {self.timeout}s")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()

    def __del__(self):
        """Cleanup on deletion."""
        self.release()


class KnowledgeMapLock:
    """Specialized lock for knowledge map operations."""

    def __init__(self, directory: str = ".", timeout: float = 30.0):
        """Initialize knowledge map lock.

        Args:
            directory: Directory containing knowledge_map.yaml
            timeout: Maximum time to wait for lock (seconds)
        """
        self.directory = Path(directory)
        lock_file = self.directory / ".knowledge_map.lock"
        self.lock = FileLock(str(lock_file), timeout=timeout)

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire lock for knowledge map operations.

        Args:
            blocking: If True, wait until lock is available

        Returns:
            True if lock acquired, False otherwise
        """
        return self.lock.acquire(blocking=blocking)

    def release(self):
        """Release the lock."""
        self.lock.release()

    def is_locked_by_another_process(self) -> bool:
        """Check if knowledge map is locked by another process.

        Returns:
            True if locked by another process, False otherwise
        """
        lock_file = self.directory / ".knowledge_map.lock"

        if not lock_file.exists():
            return False

        try:
            # Try to read PID from lock file
            with open(lock_file, 'r') as f:
                lock_pid = int(f.read().strip())

            # Check if process is still running
            if os.name == 'nt':
                # Windows - check if process exists
                import subprocess
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {lock_pid}'],
                    capture_output=True,
                    text=True
                )
                return str(lock_pid) in result.stdout
            else:
                # Unix/Linux - send signal 0 to check if process exists
                try:
                    os.kill(lock_pid, 0)
                    return True
                except OSError:
                    return False

        except:
            # If we can't determine, assume it's locked
            return True

    def __enter__(self):
        """Context manager entry."""
        return self.lock.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return self.lock.__exit__(exc_type, exc_val, exc_tb)


def check_knowledge_map_lock(directory: str = ".") -> Optional[str]:
    """Check if knowledge map is locked and return warning message.

    Args:
        directory: Directory containing knowledge_map.yaml

    Returns:
        Warning message if locked, None otherwise
    """
    lock = KnowledgeMapLock(directory)

    if lock.is_locked_by_another_process():
        return (
            "⚠️  Knowledge map is being rebuilt by another process.\n"
            "Please wait for it to complete or use Ctrl+C to force rebuild."
        )

    return None
