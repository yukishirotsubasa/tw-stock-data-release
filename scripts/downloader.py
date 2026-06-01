"""
TWSE MI_INDEX 每日行情下載器
- Rate limiting (固定間隔 + exponential backoff)
- 重試機制
"""
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
import logging
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def download_day(
    date_str: str,
    save_dir: str | Path = config.DATA_DIR,
    max_retries: int = config.MAX_RETRIES,
    force_redownload: bool = False,
) -> Path | None:
    """
    下載指定日期的 MI_INDEX JSON 並儲存至本地檔案。

    Args:
        date_str: 日期字串 YYYYMMDD
        save_dir: 儲存目錄
        max_retries: 下載重試次數（至少 1）
        force_redownload: True 時忽略本地既有檔案並強制重抓

    Returns:
        儲存的檔案路徑，失敗時回傳 None
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / f"{date_str}.json"

    # 已存在就跳過 (idempotent)
    if filepath.exists() and not force_redownload:
        logger.info(f"[SKIP] {date_str} 已存在")
        return filepath

    url = config.TWSE_MI_INDEX_URL.format(date=date_str)
    retry_count = max(1, int(max_retries))

    for attempt in range(1, retry_count + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")

            # 嘗試解析 JSON 確認格式正確
            json.loads(raw)

            filepath.write_text(raw, encoding="utf-8")
            logger.info(f"[OK] {date_str} 已下載 ({len(raw):,} bytes)")
            return filepath

        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = config.BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                logger.warning(
                    f"[RETRY {attempt}/{retry_count}] {date_str} "
                    f"HTTP {e.code}, 等待 {wait}s"
                )
                time.sleep(wait)
            else:
                logger.error(f"[FAIL] {date_str} HTTP {e.code}: {e.reason}")
                return None

        except (urllib.error.URLError, TimeoutError) as e:
            wait = config.BACKOFF_BASE_SEC * (2 ** (attempt - 1))
            logger.warning(
                f"[RETRY {attempt}/{retry_count}] {date_str} "
                f"連線錯誤: {e}, 等待 {wait}s"
            )
            time.sleep(wait)

    logger.error(f"[FAIL] {date_str} 重試 {retry_count} 次後放棄")
    return None


def download_days(
    date_list: list[str],
    save_dir: str | Path = config.DATA_DIR,
    delay: float = config.REQUEST_DELAY_SEC,
) -> dict[str, Path | None]:
    """
    批次下載多個日期，每次間隔 delay 秒。

    Returns:
        dict: {date_str: filepath_or_None}
    """
    results = {}
    for i, date_str in enumerate(date_list):
        if i > 0:
            logger.debug(f"等待 {delay}s...")
            time.sleep(delay)

        results[date_str] = download_day(date_str, save_dir)

    return results
