"""
TPEX 上櫃股票每日收盤行情下載器。
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/html,*/*",
}


def build_tpex_otc_url(date_str: str) -> str:
    date = datetime.strptime(date_str, "%Y%m%d")
    query = urllib.parse.urlencode(
        {
            "date": date.strftime("%Y/%m/%d"),
            "type": "AL",
            "id": "",
            "response": "csv",
            "order": "0",
            "sort": "asc",
        }
    )
    return f"{config.TPEX_OTC_URL}?{query}"


def download_tpex_day(
    date_str: str,
    save_dir: str | Path = config.TPEX_DATA_DIR,
    max_retries: int = config.MAX_RETRIES,
    force_redownload: bool = False,
) -> Path | None:
    """
    下載指定日期的 TPEX OTC CSV 原始資料。
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / f"{date_str}.csv"

    if filepath.exists() and not force_redownload:
        logger.info(f"[SKIP][TPEX] {date_str} 已存在")
        return filepath

    url = build_tpex_otc_url(date_str)
    retry_count = max(1, int(max_retries))

    for attempt in range(1, retry_count + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()

            if not raw:
                logger.warning(f"[RETRY {attempt}/{retry_count}][TPEX] {date_str} 空回應")
                continue

            filepath.write_bytes(raw)
            logger.info(f"[OK][TPEX] {date_str} 已下載 ({len(raw):,} bytes)")
            return filepath

        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = config.BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                logger.warning(
                    f"[RETRY {attempt}/{retry_count}][TPEX] {date_str} "
                    f"HTTP {e.code}, 等待 {wait}s"
                )
                time.sleep(wait)
            else:
                logger.error(f"[FAIL][TPEX] {date_str} HTTP {e.code}: {e.reason}")
                return None

        except (urllib.error.URLError, TimeoutError) as e:
            wait = config.BACKOFF_BASE_SEC * (2 ** (attempt - 1))
            logger.warning(
                f"[RETRY {attempt}/{retry_count}][TPEX] {date_str} "
                f"連線錯誤: {e}, 等待 {wait}s"
            )
            time.sleep(wait)

    logger.error(f"[FAIL][TPEX] {date_str} 重試 {retry_count} 次後放棄")
    return None
