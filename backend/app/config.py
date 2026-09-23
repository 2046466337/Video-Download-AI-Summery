"""全局配置：路径、并发、清理策略、外部工具定位。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
DB_PATH = DATA_DIR / "app.db"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

# 会员内容与需登录的高清源要靠 cookies：放 data/cookies/<域名>.txt 或 data/cookies.txt
COOKIES_DIR = DATA_DIR / "cookies"
GLOBAL_COOKIES_FILE = DATA_DIR / "cookies.txt"

# yt-dlp 是同步阻塞的，必须放进线程池；并发过高会把带宽和磁盘打满
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))

# 下载产物保留时长，超时由后台线程清理，避免磁盘被撑爆
FILE_TTL_HOURS = float(os.getenv("FILE_TTL_HOURS", "6"))
CLEAN_INTERVAL_SECONDS = 30 * 60

SOCKET_TIMEOUT = 20

# 合并音视频轨必须依赖 FFmpeg，找不到时只能下单文件流
_ffmpeg = os.getenv("FFMPEG_LOCATION") or shutil.which("ffmpeg")
FFMPEG_LOCATION = str(Path(_ffmpeg).parent) if _ffmpeg else None

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
COOKIES_DIR.mkdir(parents=True, exist_ok=True)
