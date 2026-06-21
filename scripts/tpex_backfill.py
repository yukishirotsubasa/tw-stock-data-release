"""
TPEX local backfill and packaging tool.

This script only reads local source files. It does not download data.

Supported source formats:
- HTML files before 2007-07, for example `YYYYMMDD.txt`
- CSV-like text files from 2007-07 onward, for example `YYYYMMDD.txt`

Usage:
    python -m scripts.tpex_backfill --source-dir "tpex sample" --start 20070102 --end 20070707
    python -m scripts.tpex_backfill --source-dir tpex_raw --output-dir output_tpex --zip-dir releases_tpex
    python -m scripts.tpex_backfill --merge-only --merge-period year --output-dir output_tpex --zip-dir releases_tpex

Arguments:
- `--start`: start date, `YYYYMMDD`. Default: `20070102`
- `--end`: end date, `YYYYMMDD`. Default: `20260404`
- `--source-dir`: local source directory containing `YYYYMMDD.txt` or `YYYYMMDD.csv`. Default: `.`
- `--output-dir`: daily CSV output directory. Default: `output_tpex`
- `--zip-dir`: merged zip output directory. Default: `releases_tpex`
- `--merge-period`: packaging period, `week` or `year`. Default: `week`
- `--extract-only`: output daily CSV files only, no merge or zip.
- `--validation-log`: invalid source log path. Default: `logs/tpex_validation_failures.log`
- `--merge-only`: skip source parsing and only merge existing daily CSV files.

Generated files:
- Daily CSV: `{output-dir}/YYYYMMDD.csv`
- Weekly zip: `{zip-dir}/weekly_YYYY_Www.zip`
- Yearly zip: `{zip-dir}/yearly_YYYY.zip`
- Validation failures: `{validation-log}`
"""
from __future__ import annotations

import argparse
import csv
import html
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config
from scripts.merger import merge_and_zip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_START = "20070102"
DEFAULT_END = "20260404"
DEFAULT_OUTPUT_DIR = "output_tpex"
DEFAULT_ZIP_DIR = "releases_tpex"
DEFAULT_VALIDATION_LOG = "logs/tpex_validation_failures.log"

DATE_HTML_RE = re.compile(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日")
DATE_CSV_RE = re.compile(r"資料日期\s*:\s*(\d{2,3})/(\d{1,2})/(\d{1,2})")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

FIELD_ALIASES = {
    "code": "代號",
    "name": "名稱",
    "close": "收盤",
    "open": "開盤",
    "high": "最高",
    "low": "最低",
    "volume": "成交股數",
}


class ValidationError(Exception):
    """Raised when a local TPEX source file is malformed."""


class TpexHtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._current_row = []
        elif tag.lower() in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._current_cell is not None:
            value = normalize_cell("".join(self._current_cell))
            if self._current_row is not None:
                self._current_row.append(value)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None


def read_source_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("無法以 utf-8/cp950/big5 解碼")


def normalize_cell(value: str) -> str:
    return html.unescape(value).replace("\xa0", " ").strip()


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", "", normalize_cell(value))


def roc_to_yyyymmdd(year: str, month: str, day: str) -> str:
    return f"{int(year) + 1911:04d}{int(month):02d}{int(day):02d}"


def parse_source_date(text: str) -> str | None:
    csv_match = DATE_CSV_RE.search(text)
    if csv_match:
        return roc_to_yyyymmdd(*csv_match.groups())

    html_match = DATE_HTML_RE.search(text)
    if html_match:
        return roc_to_yyyymmdd(*html_match.groups())

    return None


def clean_number(value: str) -> str:
    compact = normalize_cell(value).replace(",", "")
    if not compact or compact in {"--", "---"}:
        return ""

    match = NUMBER_RE.search(compact)
    return match.group(0) if match else ""


def is_tpex_security(code: str, name: str) -> bool:
    return config.is_included_security(normalize_cell(code), normalize_cell(name))


def make_record(date_str: str, values: dict[str, str]) -> dict[str, str]:
    return {
        "date": date_str,
        "code": normalize_cell(values["code"]),
        "name": normalize_cell(values["name"]),
        "volume": clean_number(values["volume"]),
        "open": clean_number(values["open"]),
        "high": clean_number(values["high"]),
        "low": clean_number(values["low"]),
        "close": clean_number(values["close"]),
    }


def parse_html_rows(text: str, date_str: str) -> list[dict[str, str]]:
    parser = TpexHtmlTableParser()
    parser.feed(text)

    records: list[dict[str, str]] = []
    for row in parser.rows:
        if len(row) < 8 or not is_tpex_security(row[0], row[1]):
            continue

        record = make_record(
            date_str,
            {
                "code": row[0],
                "name": row[1],
                "close": row[2],
                "open": row[4],
                "high": row[5],
                "low": row[6],
                "volume": row[7],
            },
        )
        records.append(record)

    return records


def find_csv_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    for row_index, row in enumerate(rows):
        normalized = [normalize_header(cell) for cell in row]
        if "代號" not in normalized or "名稱" not in normalized:
            continue

        indices: dict[str, int] = {}
        for output_name, source_name in FIELD_ALIASES.items():
            try:
                indices[output_name] = normalized.index(source_name)
            except ValueError as e:
                raise ValidationError(f"CSV 缺少欄位: {source_name}") from e

        return row_index, indices

    raise ValidationError("找不到 CSV header")


def parse_csv_rows(text: str, date_str: str) -> list[dict[str, str]]:
    rows = list(csv.reader(text.splitlines()))
    header_index, indices = find_csv_header(rows)
    records: list[dict[str, str]] = []

    for row in rows[header_index + 1 :]:
        if len(row) == 1 and normalize_cell(row[0]).startswith("共0筆"):
            continue

        if len(row) <= max(indices.values()):
            continue

        code = row[indices["code"]]
        name = row[indices["name"]]
        if not is_tpex_security(code, name):
            continue

        record = make_record(
            date_str,
            {name: row[index] for name, index in indices.items()},
        )
        records.append(record)

    return records


def extract_tpex_day(path: str | Path, expected_date: str) -> list[dict[str, str]]:
    path = Path(path)
    text = read_source_text(path)
    source_date = parse_source_date(text)

    if source_date != expected_date:
        raise ValidationError(f"date mismatch: expected {expected_date}, got {source_date}")

    if "<table" in text.lower():
        records = parse_html_rows(text, expected_date)
    else:
        records = parse_csv_rows(text, expected_date)

    logger.info(f"[EXTRACT] {expected_date}: {len(records)} rows")
    return records


def save_csv(rows: list[dict[str, str]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"[CSV] {path} ({len(rows)} rows)")
    return path


def generate_dates(start: str, end: str) -> Iterator[str]:
    current = datetime.strptime(start, "%Y%m%d")
    final = datetime.strptime(end, "%Y%m%d")
    while current <= final:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def count_dates(start: str, end: str) -> int:
    current = datetime.strptime(start, "%Y%m%d")
    final = datetime.strptime(end, "%Y%m%d")
    if final < current:
        return 0
    return (final - current).days + 1


def find_source_file(source_dir: Path, date_str: str) -> Path | None:
    for suffix in (".txt", ".csv", ".html", ".htm"):
        path = source_dir / f"{date_str}{suffix}"
        if path.exists():
            return path
    return None


def append_validation_failure(log_path: Path, date_str: str, reason: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{date_str}\t{reason}\n")


def run_extract(
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
            logger.info(f"[SKIP] {date_str} CSV exists ({i}/{total})")
            success_dates.append(date_str)
            continue

        source_path = find_source_file(source_dir, date_str)
        if source_path is None:
            logger.info(f"[SKIP] {date_str} no source ({i}/{total})")
            continue

        try:
            rows = extract_tpex_day(source_path, date_str)
        except ValidationError as e:
            logger.info(f"[SKIP] {date_str} validation failed: {e} ({i}/{total})")
            append_validation_failure(validation_log, date_str, str(e))
            continue

        if not rows:
            logger.info(f"[SKIP] {date_str} no data rows ({i}/{total})")
            continue

        save_csv(rows, csv_path)
        success_dates.append(date_str)

    return success_dates


def group_csv_files(csv_files: list[Path], merge_period: str) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)

    for f in csv_files:
        d = datetime.strptime(f.stem, "%Y%m%d")
        if merge_period == "week":
            iso_year, iso_week, _ = d.isocalendar()
            key = f"{iso_year}_W{iso_week:02d}"
        elif merge_period == "year":
            key = f"{d.year}"
        else:
            raise ValueError(f"Unsupported merge_period: {merge_period}")

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
    ranged_files = [
        f
        for f in csv_files
        if len(f.stem) == 8 and f.stem.isdigit() and start <= f.stem <= end
    ]

    if not ranged_files:
        logger.error(f"No CSV files in range {start} ~ {end}")
        return

    groups = group_csv_files(ranged_files, merge_period)
    logger.info(f"Merge {len(ranged_files)} CSV files into {len(groups)} {merge_period} groups")

    for group_key, files in groups.items():
        if merge_period == "year":
            tag = f"yearly_{group_key}"
        else:
            tag = f"weekly_{group_key}"

        zip_path = zip_dir / f"{tag}.zip"
        if zip_path.exists():
            logger.info(f"[SKIP] {zip_path} exists")
            continue

        merge_and_zip(files, tag, zip_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="TPEX local backfill and packaging tool")
    parser.add_argument("--start", default=DEFAULT_START, help="Start date YYYYMMDD")
    parser.add_argument("--end", default=DEFAULT_END, help="End date YYYYMMDD")
    parser.add_argument("--source-dir", default=".", help="Local source directory")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Daily CSV output directory")
    parser.add_argument("--zip-dir", default=DEFAULT_ZIP_DIR, help="Merged zip output directory")
    parser.add_argument("--merge-period", choices=["week", "year"], default="week", help="Merge period")
    parser.add_argument("--extract-only", action="store_true", help="Only convert raw data to daily CSV files")
    parser.add_argument("--validation-log", default=DEFAULT_VALIDATION_LOG, help="Validation failure log")
    parser.add_argument("--merge-only", action="store_true", help="Only merge existing daily CSV files")
    args = parser.parse_args()

    if args.merge_only and args.extract_only:
        parser.error("--merge-only and --extract-only cannot be used together")

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    zip_dir = Path(args.zip_dir)
    validation_log = Path(args.validation_log)

    if args.merge_only:
        run_merge(output_dir, zip_dir, args.merge_period, args.start, args.end)
        return

    total = count_dates(args.start, args.end)
    success = run_extract(
        generate_dates(args.start, args.end),
        source_dir,
        output_dir,
        validation_log,
        total,
    )
    logger.info(f"Extracted {len(success)}/{total} dates")
    if args.extract_only:
        logger.info("extract-only: skip merge/zip")
        return

    run_merge(output_dir, zip_dir, args.merge_period, args.start, args.end)


if __name__ == "__main__":
    main()
