"""
TWSE/TPEX 每日 CSV 合併打包工具。

此工具只讀取已轉換完成的 CSV，不讀取、不驗證 raw data。

輸入檔案:
- TWSE 每日 CSV: `{twse-dir}/YYYYMMDD.csv`
- TPEX 每日 CSV: `{tpex-dir}/YYYYMMDD.csv`

建議先使用 `scripts.backfill --extract-only` 與
`scripts.tpex_backfill --extract-only` 產生每日 CSV，避免先產生各市場獨立 zip。

用法:
    python -m scripts.merge_markets --twse-dir output --tpex-dir output_tpex --output-dir releases_all
    python -m scripts.merge_markets --merge-period year --start 20070101 --end 20071231

產生檔案:
- `{output-dir}/weekly_YYYY_Www.zip`
- `{output-dir}/yearly_YYYY.zip`
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.merger import merge_and_zip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_START = "20040211"
DEFAULT_END = "20260404"
DEFAULT_TWSE_DIR = "output"
DEFAULT_TPEX_DIR = "output_tpex"
DEFAULT_OUTPUT_DIR = "releases_all"


def collect_daily_csvs(csv_dir: Path, start: str, end: str) -> list[Path]:
    files: list[Path] = []

    for path in sorted(csv_dir.glob("*.csv")):
        date_str = path.stem
        if len(date_str) != 8 or not date_str.isdigit():
            continue
        if start <= date_str <= end:
            files.append(path)

    return files


def group_csv_files(csv_files: list[Path], merge_period: str) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)

    for path in csv_files:
        date = datetime.strptime(path.stem, "%Y%m%d")
        if merge_period == "week":
            iso_year, iso_week, _ = date.isocalendar()
            tag = f"weekly_{iso_year}_W{iso_week:02d}"
        elif merge_period == "year":
            tag = f"yearly_{date.year}"
        else:
            raise ValueError(f"Unsupported merge_period: {merge_period}")

        groups[tag].append(path)

    return dict(sorted(groups.items()))


def run_merge(
    twse_dir: Path,
    tpex_dir: Path,
    output_dir: Path,
    merge_period: str,
    start: str,
    end: str,
) -> None:
    csv_files = collect_daily_csvs(twse_dir, start, end)
    csv_files.extend(collect_daily_csvs(tpex_dir, start, end))

    if not csv_files:
        logger.error(f"找不到區間 {start} ~ {end} 的每日 CSV")
        return

    groups = group_csv_files(csv_files, merge_period)
    logger.info(f"Merge {len(csv_files)} daily CSV files into {len(groups)} {merge_period} zip packages")

    for tag, files in groups.items():
        zip_path = output_dir / f"{tag}.zip"
        if zip_path.exists():
            logger.info(f"[SKIP] {zip_path} exists")
            continue

        merge_and_zip(files, tag, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="合併 TWSE/TPEX 每日 CSV 並產生 zip")
    parser.add_argument("--twse-dir", default=DEFAULT_TWSE_DIR, help="TWSE 每日 CSV 目錄")
    parser.add_argument("--tpex-dir", default=DEFAULT_TPEX_DIR, help="TPEX 每日 CSV 目錄")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="合併後 zip 輸出目錄")
    parser.add_argument("--merge-period", choices=["week", "year"], default="week", help="輸出合併週期")
    parser.add_argument("--start", default=DEFAULT_START, help="起始日期 YYYYMMDD")
    parser.add_argument("--end", default=DEFAULT_END, help="結束日期 YYYYMMDD")
    args = parser.parse_args()

    run_merge(
        Path(args.twse_dir),
        Path(args.tpex_dir),
        Path(args.output_dir),
        args.merge_period,
        args.start,
        args.end,
    )


if __name__ == "__main__":
    main()
