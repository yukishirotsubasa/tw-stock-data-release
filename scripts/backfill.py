"""
歷史資料回填與批次打包工具。

流程:
1. 依日期區間尋找原始檔 (`YYYYMMDD.txt` 或 `YYYYMMDD.json`)
2. 驗證後轉成每日 CSV 到 output 目錄
3. 依 `--merge-period` 合併並打包 zip 到 zip 目錄

輸出命名:
- 每日 CSV: {output-dir}/YYYYMMDD.csv
- 週包: {zip-dir}/weekly_YYYY_Www.zip
- 年包: {zip-dir}/yearly_YYYY.zip
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config
from scripts.validator import validate, ValidationError
from scripts.extractor import extract_and_save
from scripts.merger import merge_and_zip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_START = "20040211"
DEFAULT_END = "20260404"


def generate_dates(start: str, end: str) -> Iterator[str]:
    s = datetime.strptime(start, "%Y%m%d")
    e = datetime.strptime(end, "%Y%m%d")
    current = s
    while current <= e:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def count_dates(start: str, end: str) -> int:
    s = datetime.strptime(start, "%Y%m%d")
    e = datetime.strptime(end, "%Y%m%d")
    if e < s:
        return 0
    return (e - s).days + 1


def find_source_file(source_dir: Path, date_str: str) -> Path | None:
    txt_path = source_dir / f"{date_str}.txt"
    if txt_path.exists():
        return txt_path

    json_path = source_dir / f"{date_str}.json"
    if json_path.exists():
        return json_path

    return None


def append_validation_failure(log_path: Path, date_str: str, reason: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{date_str}\t{reason}\n")


def run_read_and_extract(
    dates: Iterable[str],
    source_dir: Path,
    output_dir: Path,
    validation_log: Path,
    total: int,
) -> list[str]:
    success_dates: list[str] = []

    for i, date_str in enumerate(dates, start=1):
        csv_path = output_dir / f"{date_str}.csv"

        if csv_path.exists():
            logger.info(f"[SKIP] {date_str} CSV 已存在 ({i}/{total})")
            success_dates.append(date_str)
            continue

        filepath = find_source_file(source_dir, date_str)
        if filepath is None:
            logger.info(f"[SKIP] {date_str} 無來源檔 ({i}/{total})")
            continue

        try:
            validate(filepath, date_str)
        except ValidationError as e:
            logger.info(f"[SKIP] {date_str} 驗證失敗: {e} ({i}/{total})")
            append_validation_failure(validation_log, date_str, str(e))
            continue

        result = extract_and_save(filepath, date_str, output_dir)
        if result:
            success_dates.append(date_str)
            logger.info(f"進度: {i}/{total} ({len(success_dates)} 成功)")

    return success_dates


def group_csv_files(csv_files: list[Path], merge_period: str) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)

    for f in csv_files:
        date_str = f.stem
        d = datetime.strptime(date_str, "%Y%m%d")

        if merge_period == "week":
            iso_year, iso_week, _ = d.isocalendar()
            key = f"{iso_year}_W{iso_week:02d}"
        elif merge_period == "year":
            key = f"{d.year}"
        else:
            raise ValueError(f"不支援的 merge_period: {merge_period}")

        groups[key].append(f)

    return dict(sorted(groups.items()))


def run_merge(
    output_dir: Path,
    zip_dir: Path,
    merge_period: str,
    start: str,
    end: str,
) -> None:
    csv_files = sorted(output_dir.glob("*.csv"))
    if not csv_files:
        logger.error("找不到任何 CSV 可供合併")
        return

    ranged_files: list[Path] = []
    for f in csv_files:
        date_str = f.stem
        if len(date_str) != 8 or not date_str.isdigit():
            continue
        if start <= date_str <= end:
            ranged_files.append(f)

    if not ranged_files:
        logger.error(f"區間 {start} ~ {end} 內沒有可用 CSV")
        return

    groups = group_csv_files(ranged_files, merge_period)
    logger.info(f"區間內共 {len(ranged_files)} 個 CSV, {len(groups)} 個 {merge_period} 群組")

    for group_key, files in sorted(groups.items()):
        if merge_period == "year":
            tag = f"yearly_{group_key}"
        elif merge_period == "week":
            tag = f"weekly_{group_key}"
        else:
            dates = [f.stem for f in files]
            tag = f"{dates[0]}-{dates[-1]}"

        zip_path = zip_dir / f"{tag}.zip"
        if zip_path.exists():
            logger.info(f"[SKIP] {tag}.zip 已存在")
            continue

        merge_and_zip(files, tag, zip_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="TWSE 歷史資料回填工具")
    parser.add_argument("--start", default=DEFAULT_START, help="起始日期 YYYYMMDD")
    parser.add_argument("--end", default=DEFAULT_END, help="結束日期 YYYYMMDD")
    parser.add_argument("--merge-only", action="store_true", help="只做合併打包，不做抽取")
    parser.add_argument("--source-dir", default=".", help="來源檔目錄 (YYYYMMDD.txt/json)")
    parser.add_argument("--output-dir", default=config.OUTPUT_DIR, help="CSV 輸出目錄")
    parser.add_argument("--zip-dir", default="releases", help="Zip 輸出目錄")
    parser.add_argument("--merge-period", choices=["week", "year"], default="week", help="合併週期")
    parser.add_argument("--validation-log", default="logs/validation_failures.log", help="驗證失敗紀錄")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    zip_dir = Path(args.zip_dir)
    validation_log = Path(args.validation_log)

    if args.merge_only:
        logger.info("=== Merge Only ===")
        run_merge(output_dir, zip_dir, args.merge_period, args.start, args.end)
        return

    total = count_dates(args.start, args.end)
    dates = generate_dates(args.start, args.end)
    logger.info(f"日期區間: {args.start} ~ {args.end}")
    logger.info(f"日期總數: {total}")
    logger.info(f"來源目錄: {source_dir}")
    logger.info(f"驗證失敗紀錄: {validation_log}")

    success = run_read_and_extract(dates, source_dir, output_dir, validation_log, total)
    logger.info(f"抽取完成: {len(success)}/{total} 成功")

    logger.info("=== Merge ===")
    run_merge(output_dir, zip_dir, args.merge_period, args.start, args.end)
    logger.info("全部完成")


if __name__ == "__main__":
    main()
