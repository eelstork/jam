"""BFS file finder across jam repos."""

import os
from collections import deque


_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
_MAX_RESULTS = 10


def find_file(filename, search_roots):
    """BFS search for *filename* under each directory in *search_roots*.

    Returns a list of absolute paths (at most ``_MAX_RESULTS + 1`` to
    allow the caller to detect overflow).  Skips common noise
    directories.
    """
    results = []
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        queue = deque([root])
        while queue:
            if len(results) > _MAX_RESULTS:
                return results
            current = queue.popleft()
            try:
                entries = os.scandir(current)
            except PermissionError:
                continue
            dirs = []
            for entry in entries:
                if entry.is_file(follow_symlinks=False) and entry.name == filename:
                    results.append(entry.path)
                elif entry.is_dir(follow_symlinks=False) and entry.name not in _SKIP_DIRS:
                    dirs.append(entry.path)
            dirs.sort()
            queue.extend(dirs)
    return results
