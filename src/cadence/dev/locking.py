import os
import sys
import warnings

class FileMutex:
    """
    Context manager for cross-process file-based mutex locking.

    On POSIX, uses fcntl.flock for advisory locking.
    On Windows, uses msvcrt.locking for exclusive file locks.
    On unsupported platforms, acts as a stub and issues a warning.

    Attributes:
        path (str): Path to the lock file (<target_path>.lock)
        acquired (bool): True if the lock is held by this context, else False.

    Example:
        >>> with FileMutex('/tmp/myresource') as mtx:
        ...     if mtx.acquired:
        ...         # critical section
        ...         pass

    Notes:
        - Lock files are named <target_path>.lock
        - Lock is released on exit from context
        - Advisory: all cooperating processes must use this mechanism
    """
    def __init__(self, target_path):
        self._file = None
        self.acquired = False
        self.path = f"{target_path}.lock"

    def __enter__(self):
        if sys.platform.startswith('linux') or sys.platform.startswith('darwin') or 'bsd' in sys.platform:
            try:
                import fcntl
                self._file = open(self.path, 'w')
                fcntl.flock(self._file, fcntl.LOCK_EX)
                self.acquired = True
            except Exception as e:
                warnings.warn(f"FileMutex failed to acquire POSIX lock: {e}")
                self.acquired = False
        elif sys.platform.startswith('win'):
            try:
                import msvcrt
                self._file = open(self.path, 'a+')
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
                self.acquired = True
            except Exception as e:
                warnings.warn(f"FileMutex failed to acquire Windows lock: {e}")
                self.acquired = False
        else:
            warnings.warn(f"FileMutex: Platform {sys.platform} not supported; lock is a no-op.")
            self.acquired = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if sys.platform.startswith('linux') or sys.platform.startswith('darwin') or 'bsd' in sys.platform:
            try:
                if self._file:
                    import fcntl
                    fcntl.flock(self._file, fcntl.LOCK_UN)
                    self._file.close()
            except Exception:
                pass
        elif sys.platform.startswith('win'):
            try:
                if self._file:
                    import msvcrt
                    self._file.seek(0)
                    msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
                    self._file.close()
            except Exception:
                pass
        self.acquired = False
        self._file = None
