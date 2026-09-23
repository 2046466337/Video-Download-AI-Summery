"""过期产物清理。

下载文件留在磁盘上是纯成本，没有清理机制的话服务跑几天就会被撑爆。
"""

from __future__ import annotations

import shutil
import threading
import time

from .config import CLEAN_INTERVAL_SECONDS, DOWNLOAD_DIR, FILE_TTL_HOURS


def purge_expired() -> int:
    if not DOWNLOAD_DIR.exists():
        return 0

    deadline = time.time() - FILE_TTL_HOURS * 3600
    removed = 0
    for entry in DOWNLOAD_DIR.iterdir():
        try:
            if entry.stat().st_mtime < deadline:
                shutil.rmtree(entry, ignore_errors=True) if entry.is_dir() else entry.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    return removed


def start_cleaner(stop_event: threading.Event) -> threading.Thread:
    def loop() -> None:
        purge_expired()
        while not stop_event.wait(CLEAN_INTERVAL_SECONDS):
            purge_expired()

    thread = threading.Thread(target=loop, name="cleaner", daemon=True)
    thread.start()
    return thread
