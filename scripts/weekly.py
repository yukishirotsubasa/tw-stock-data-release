"""
每週更新主程式 (GitHub Actions 使用)

計算上週一～週五的日期，逐日下載→驗證→擷取→合併→打包 zip。
"""
from __future__ import annotations
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 允許從專案根目錄執行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config
from scripts.downloader import download_days
from scripts.validator import validate, ValidationError
from scripts.extractor import extract_and_save
from scripts.merger import merge_and_zip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)
DATASET_TAG = "daily-close-csv"


def write_github_output(
    tag: str,
    zip_path: Path,
    package_tag: str,
    period_start: str,
    period_end: str,
) -> None:
    """將輸出寫入 GitHub Actions output 檔案。"""
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return

    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"tag={tag}\n")
        f.write(f"zip_path={zip_path}\n")
        f.write(f"package_tag={package_tag}\n")
        f.write(f"period_start={period_start}\n")
        f.write(f"period_end={period_end}\n")


def get_last_week_dates(ref_date: datetime | None = None) -> list[str]:
    """取得上週一～週五的日期字串列表"""
    if ref_date is None:
        ref_date = datetime.now()

    # 找到上週一
    days_since_monday = ref_date.weekday()  # 0=Mon
    this_monday = ref_date - timedelta(days=days_since_monday)
    if days_since_monday >= 5:  # Sat/Sun
        last_monday = this_monday
    else:
        last_monday = this_monday - timedelta(days=7)

    dates = []
    for i in range(5):  # Mon ~ Fri
        d = last_monday + timedelta(days=i)
        dates.append(d.strftime("%Y%m%d"))

    return dates


def get_weekly_package_tag(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y%m%d")
    iso_year, iso_week, _ = d.isocalendar()
    return f"weekly_{iso_year}_W{iso_week:02d}"


def run(ref_date: datetime | None = None):
    dates = get_last_week_dates(ref_date)
    logger.info(f"目標日期: {dates[0]} ~ {dates[-1]}")

    # 1. 下載
    logger.info("=== Phase 1: 下載 ===")
    results = download_days(dates)

    # 2. 驗證 + 擷取
    logger.info("=== Phase 2: 驗證 + 擷取 ===")
    csv_paths = []
    valid_dates = []

    for date_str, filepath in results.items():
        if filepath is None:
            logger.warning(f"[SKIP] {date_str} 下載失敗")
            continue

        try:
            validate(filepath, date_str)
        except ValidationError as e:
            logger.warning(f"[SKIP] {date_str} 驗證失敗: {e}")
            continue

        csv_path = extract_and_save(filepath, date_str)
        if csv_path:
            csv_paths.append(csv_path)
            valid_dates.append(date_str)

    if not csv_paths:
        logger.error("本週沒有有效的交易日資料")
        sys.exit(1)

    # 3. 合併 + 打包
    logger.info("=== Phase 3: 合併 + 打包 ===")
    valid_dates.sort()
    package_tag = get_weekly_package_tag(valid_dates[0])
    tag = f"{DATASET_TAG}"
    zip_path = merge_and_zip(csv_paths, package_tag)

    logger.info(f"完成! zip: {zip_path}")
    logger.info(f"Release tag: {tag}")

    # 輸出給 GitHub Actions 使用
    write_github_output(tag, zip_path, package_tag, valid_dates[0], valid_dates[-1])

    return tag, zip_path


if __name__ == "__main__":
    # 可傳入參考日期，預設為今天
    if len(sys.argv) > 1:
        ref = datetime.strptime(sys.argv[1], "%Y%m%d")
    else:
        ref = None

    run(ref)
