"""
FileMutex: Cross-process exclusive file lock for POSIX and Windows.

- POSIX: Uses fcntl.flock
- Windows: Uses msvcrt.locking
- Others: No-op with warning

Example Usage:
    from cadence.dev.locking import FileMutex
    with FileMutex('/tmp/somefile') as lock:
        if lock.acquired:
            # Do work exclusively
"""
import os
import sys
import warnings

class FileMutex:
    """
    Cross-process file-based exclusive lock using system lock primitives.
    Creates a lock file at <target_path>.lock (does not modify target_path).
    Platform Support:
      - POSIX: Uses fcntl.flock
      - Windows: Uses msvcrt.locking
      - Other: No-op stub; emits warning, never acquires lock

    Attributes:
        path (str): Path to lock file
        acquired (bool): True if lock was acquired
    """
    def __init__(self, target_path):
        self.path = os.path.abspath(target_path) + '.lock'
        self._fh = None
        self.acquired = False
        self._platform = sys.platform
        self._is_posix = self._platform != 'win32'
        self._is_windows = self._platform == 'win32'
        self._stub = not (self._is_posix or self._is_windows)

    def __enter__(self):
        if self._is_posix:
            import fcntl
            self._fh = open(self.path, 'w')
            try:
                fcntl.flock(self._fh, fcntl.LOCK_EX)
                self.acquired = True
            except Exception:
                self._fh.close()
                raise
        elif self._is_windows:
            import msvcrt
            self._fh = open(self.path, 'w')
            try:
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                self.acquired = True
            except Exception:
                self._fh.close()
                raise
        else:
            warnings.warn("FileMutex: Locking is not supported on this platform. Lock is not acquired.")
            self.acquired = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_posix and self._fh:
            import fcntl
            try:
                fcntl.flock(self._fh, fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self.acquired = False
        elif self._is_windows and self._fh:
            import msvcrt
            try:
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self._fh.close()
                self.acquired = False
        else:
            self.acquired = False
        return False
