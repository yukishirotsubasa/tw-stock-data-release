"""
CSV 合併與 zip 打包。
"""
from __future__ import annotations

import csv
import logging
import zipfile
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


def merge_csvs(csv_paths: list[Path], output_csv: Path) -> Path:
    """
    合併多個每日 CSV 為單一檔案。
    - 保留單一 header
    - 內容依 (date, code) 排序
    """
    if not csv_paths:
        raise ValueError("csv_paths 不可為空")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []

    for path in csv_paths:
        if not path.exists():
            raise FileNotFoundError(f"CSV 不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_rows.append(row)

    all_rows.sort(key=lambda r: (r["date"], r["code"]))

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(f"[MERGE] {len(csv_paths)} files -> {output_csv} ({len(all_rows)} rows)")
    return output_csv


def create_zip(csv_path: Path, zip_path: Path) -> Path:
    """將 CSV 壓縮為 zip。"""
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_path, csv_path.name)

    size_mb = zip_path.stat().st_size / 1024 / 1024
    logger.info(f"[ZIP] {zip_path} ({size_mb:.2f} MB)")
    return zip_path


def merge_and_zip(
    csv_paths: list[Path],
    tag: str,
    output_dir: str | Path = config.OUTPUT_DIR,
) -> Path:
    """
    合併 CSV 並打包為 zip。

    Args:
        csv_paths: 來源 CSV 路徑列表。
        tag: 檔名識別字（例如 `weekly_2026_W15`、`yearly_2025`）。
        output_dir: 輸出目錄。

    Returns:
        zip 檔案路徑。
    """
    output_dir = Path(output_dir)
    if not csv_paths:
        raise ValueError("csv_paths 不可為空")

    merged_csv = output_dir / f"{tag}.csv"
    zip_path = output_dir / f"{tag}.zip"

    merge_csvs(csv_paths, merged_csv)
    create_zip(merged_csv, zip_path)

    # 壓縮完成後清理中間 CSV；若檔案被占用則保留並記錄 warning。
    try:
        merged_csv.unlink(missing_ok=True)
    except PermissionError:
        logger.warning(f"[CLEANUP] 無法刪除中間檔: {merged_csv}")

    return zip_path
