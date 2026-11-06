"""A media-only quota. Never apply to SQLite directories or follow links."""
import time
from pathlib import Path


def prune_media(root, *, max_bytes=512 * 1024 * 1024, max_age=30 * 86400, now=None):
    now = time.time() if now is None else now
    root = Path(root)
    if not root.exists() or root.is_symlink():
        return {'bytes': 0, 'deleted': 0}
    files = []
    for item in root.rglob('*'):
        if item.is_file() and not item.is_symlink() and not any(p.is_symlink() for p in item.parents if p != root.parent):
            stat = item.stat()
            files.append((stat.st_mtime, stat.st_size, item))
    total = sum(size for _, size, _ in files)
    deleted = 0
    for at, size, path in sorted(files):
        if total <= max_bytes and now - at <= max_age:
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        total -= size
        deleted += 1
    return {'bytes': total, 'deleted': deleted}
