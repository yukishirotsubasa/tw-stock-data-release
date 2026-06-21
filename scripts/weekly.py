"""
每週更新主程式 (GitHub Actions 使用)

計算本週一～週五的日期，逐日依序處理 TWSE/TPEX，最後合併成單一 zip。
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 允許從專案根目錄執行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config
from scripts.downloader import download_day
from scripts.extractor import extract_and_save
from scripts.merger import merge_and_zip
from scripts.tpex_backfill import (
    ValidationError as TpexValidationError,
    extract_tpex_day,
    save_csv as save_tpex_csv,
)
from scripts.tpex_downloader import download_tpex_day
from scripts.validator import ValidationError, validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATASET_TAG = "daily-close-csv"
TAIPEI_TZ = timezone(timedelta(hours=8), "Asia/Taipei")
MAX_ATTEMPTS_PER_DATE = 3


def write_github_output(outputs: dict[str, str]) -> None:
    """將輸出寫入 GitHub Actions output 檔案。"""
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return

    with open(github_output, "a", encoding="utf-8") as f:
        for key, value in outputs.items():
            f.write(f"{key}={value}\n")


def get_last_week_dates(ref_date: datetime | None = None) -> list[str]:
    """取得本週一～週五的日期字串列表。"""
    if ref_date is None:
        ref_date = datetime.now(TAIPEI_TZ)
    elif ref_date.tzinfo is not None:
        ref_date = ref_date.astimezone(TAIPEI_TZ)

    days_since_monday = ref_date.weekday()
    this_monday = ref_date - timedelta(days=days_since_monday)
    if days_since_monday >= 5:
        last_monday = this_monday
    else:
        last_monday = this_monday - timedelta(days=7)

    return [
        (last_monday + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(5)
    ]


def get_weekly_package_tag(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y%m%d")
    iso_year, iso_week, _ = d.isocalendar()
    return f"weekly_{iso_year}_W{iso_week:02d}"


def is_date_mismatch_error(err_msg: str) -> bool:
    return err_msg.startswith("date mismatch:")


def is_twse_retryable_validation_error(err_msg: str) -> bool:
    if is_date_mismatch_error(err_msg):
        return True
    if err_msg.startswith("stat="):
        return False
    return True


def make_failure(market: str, date_str: str, reasons: list[str]) -> dict:
    final_status = (
        f"{market} 當日失敗達 {MAX_ATTEMPTS_PER_DATE} 次上限"
        if len(reasons) >= MAX_ATTEMPTS_PER_DATE
        else f"{market} 當日失敗(不重試條件)"
    )
    return {
        "market": market,
        "date": date_str,
        "reasons": reasons,
        "final_status": final_status,
    }


def write_failure_report(
    failed_dates: list[dict],
    success_count: int,
    total_count: int,
    period_start: str,
    period_end: str,
) -> Path:
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"weekly_failures_{period_start}_{period_end}.txt"

    repo_name = os.getenv("GITHUB_REPOSITORY", "")
    workflow_name = os.getenv("GITHUB_WORKFLOW", "Weekly TWSE/TPEX Data Update")

    lines = [
        f"專案名稱: {repo_name}",
        f"Workflow 名稱: {workflow_name}",
        f"區間: {period_start} ~ {period_end}",
        f"成功/失敗統計: {success_count}/{len(failed_dates)} (共 {total_count} 個市場日期)",
        "",
        "失敗明細:",
    ]

    for item in failed_dates:
        lines.append(f"- 市場: {item['market']}")
        lines.append(f"  日期: {item['date']}")
        for idx, reason in enumerate(item["reasons"], start=1):
            lines.append(f"  - 第{idx}次: {reason}")
        lines.append(f"  - 最終狀態: {item['final_status']}")
        lines.append("")

    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return report_path


def process_twse_day(date_str: str) -> tuple[Path | None, dict | None]:
    reasons: list[str] = []

    for attempt in range(1, MAX_ATTEMPTS_PER_DATE + 1):
        filepath = download_day(
            date_str,
            max_retries=1,
            force_redownload=(attempt > 1),
        )

        if filepath is None:
            reason = "下載失敗"
            reasons.append(reason)
            logger.warning(f"[RETRY][TWSE] {date_str} 第{attempt}/{MAX_ATTEMPTS_PER_DATE}次失敗: {reason}")
            continue

        try:
            validate(filepath, date_str)
        except ValidationError as e:
            err_msg = str(e)
            reasons.append(err_msg)

            if is_twse_retryable_validation_error(err_msg):
                logger.warning(
                    f"[RETRY][TWSE] {date_str} 第{attempt}/{MAX_ATTEMPTS_PER_DATE}次失敗: {err_msg}"
                )
                continue

            logger.warning(f"[SKIP][TWSE] {date_str} 驗證失敗(不重試): {err_msg}")
            break

        csv_path = extract_and_save(filepath, date_str, config.OUTPUT_DIR)
        if not csv_path:
            reasons.append("擷取失敗")
            logger.warning(f"[SKIP][TWSE] {date_str} 擷取失敗(不重試)")
            break

        logger.info(f"[DAY OK][TWSE] {date_str} 第{attempt}次完成")
        return csv_path, None

    return None, make_failure("TWSE", date_str, reasons)


def process_tpex_day(date_str: str) -> tuple[Path | None, dict | None]:
    reasons: list[str] = []

    for attempt in range(1, MAX_ATTEMPTS_PER_DATE + 1):
        filepath = download_tpex_day(
            date_str,
            max_retries=1,
            force_redownload=(attempt > 1),
        )

        if filepath is None:
            reason = "下載失敗"
            reasons.append(reason)
            logger.warning(f"[RETRY][TPEX] {date_str} 第{attempt}/{MAX_ATTEMPTS_PER_DATE}次失敗: {reason}")
            continue

        try:
            rows = extract_tpex_day(filepath, date_str)
        except TpexValidationError as e:
            err_msg = str(e)
            reasons.append(err_msg)
            logger.warning(
                f"[RETRY][TPEX] {date_str} 第{attempt}/{MAX_ATTEMPTS_PER_DATE}次失敗: {err_msg}"
            )
            continue

        if not rows:
            logger.info(f"[NO DATA][TPEX] {date_str} 無資料列")
            return None, None

        csv_path = Path(config.TPEX_OUTPUT_DIR) / f"{date_str}.csv"
        save_tpex_csv(rows, csv_path)
        logger.info(f"[DAY OK][TPEX] {date_str} 第{attempt}次完成")
        return csv_path, None

    return None, make_failure("TPEX", date_str, reasons)


def run_market_day(
    market: str,
    date_str: str,
) -> tuple[Path | None, dict | None]:
    if market == "TWSE":
        return process_twse_day(date_str)
    if market == "TPEX":
        return process_tpex_day(date_str)
    raise ValueError(f"不支援的市場: {market}")


def run(ref_date: datetime | None = None):
    dates = get_last_week_dates(ref_date)
    logger.info(f"目標日期: {dates[0]} ~ {dates[-1]}")

    logger.info("=== Phase 1~2: TWSE/TPEX 逐日下載 + 驗證 + 擷取 ===")
    csv_paths: list[Path] = []
    valid_dates: list[str] = []
    failed_dates: list[dict] = []
    markets = ["TWSE", "TPEX"]
    market_day_count = 0

    for date_str in dates:
        for market in markets:
            if market_day_count > 0:
                time.sleep(config.REQUEST_DELAY_SEC)
            market_day_count += 1

            csv_path, failure = run_market_day(market, date_str)
            if csv_path:
                csv_paths.append(csv_path)
                valid_dates.append(date_str)
            if failure:
                failed_dates.append(failure)
                logger.error(f"[DAY FAIL][{market}] {date_str}: {failure['final_status']}")

    tag = DATASET_TAG
    package_tag = ""
    zip_path = ""

    if csv_paths:
        logger.info("=== Phase 3: 合併 + 打包 ===")
        valid_dates.sort()
        package_tag = get_weekly_package_tag(valid_dates[0])
        zip_path = str(merge_and_zip(csv_paths, package_tag, config.OUTPUT_DIR))
        logger.info(f"完成! zip: {zip_path}")
        logger.info(f"Release tag: {tag}")
    else:
        logger.error("本週 TWSE/TPEX 沒有任何有效資料")

    has_success = bool(csv_paths)
    has_failures = bool(failed_dates)
    period_start = dates[0]
    period_end = dates[-1]
    success_count = len(csv_paths)
    failed_count = len(failed_dates)
    failure_report_path = ""

    if has_failures:
        failure_report_path = str(
            write_failure_report(
                failed_dates=failed_dates,
                success_count=success_count,
                total_count=len(dates) * len(markets),
                period_start=period_start,
                period_end=period_end,
            )
        )

    write_github_output(
        {
            "tag": tag,
            "zip_path": zip_path,
            "package_tag": package_tag,
            "period_start": period_start,
            "period_end": period_end,
            "has_success": str(has_success).lower(),
            "has_failures": str(has_failures).lower(),
            "success_count": str(success_count),
            "failed_count": str(failed_count),
            "failure_report_path": failure_report_path,
        }
    )

    if not has_success:
        sys.exit(1)

    return tag, zip_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ref = datetime.strptime(sys.argv[1], "%Y%m%d")
    else:
        ref = None

    run(ref)
