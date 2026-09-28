"""全局配置：路径、并发、清理策略、外部工具定位。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


def _load_env_file() -> None:
    """加载项目根目录 .env（只补全缺失项，不覆盖真实环境变量）。

    与 ai_client.py 的手写解析保持一致，避免引入 python-dotenv 依赖。
    这样下载并发、支付密钥等配置也都能放进 .env 统一管理。
    """
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_env_file()

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

# ---- 会员与支付（Stripe Checkout）----
# 模式：mock（本地模拟，无需外网/账号） | stripe（真实测试，需外网 + 密钥）
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "mock").strip().lower()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
# 在 Stripe Dashboard 创建的 Price 对象 ID（价格与币种都在 Dashboard 里配置）
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "").strip()
# 单次购买解锁的天数（一次性付费，到期手动续费）
MEMBERSHIP_DAYS = int(os.getenv("MEMBERSHIP_DAYS", "30"))
# 站点地址，用于 Checkout 成功/取消后的回跳
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173").rstrip("/")
