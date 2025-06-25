# ... other imports ...
from file_mutex import FileMutex
# ...
class Backlog:
    # ...
    def save(self):
        with self._lock:
            with FileMutex(self.path):
                # JSON write logic (e.g., atomic-swap save)
                # ...

    def load(self):
        with self._lock:
            with FileMutex(self.path):
                # JSON read logic
                # ...

    def _persist(self):
        with self._lock:
            with FileMutex(self.path):
                # JSON write logic
                # ...
# Remove any outdated comments about tmp-file and rename races.
