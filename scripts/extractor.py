"""
TWSE OHLCV 資料擷取器
從驗證過的 MI_INDEX JSON 擷取個股 OHLCV 並輸出為 CSV。
"""
from __future__ import annotations
import csv
import json
import logging
import re
from pathlib import Path

from . import config
from .validator import find_ohlcv_table

logger = logging.getLogger(__name__)


def clean_number(value: str) -> str:
    """
    清理數值欄位：移除千分位逗號，處理特殊值。
    '--' 或空值 → 空字串
    """
    v = value.strip()
    if not v or v == "--":
        return ""
    # 移除千分位逗號
    return v.replace(",", "")


def extract_day(filepath: str | Path, date_str: str) -> list[dict]:
    """
    從 JSON 檔案擷取 OHLCV 資料。

    Args:
        filepath: JSON 檔案路徑 (已驗證過)
        date_str: 交易日期 YYYYMMDD

    Returns:
        list of dicts, 每筆為一檔股票/ETF 的 OHLCV
    """
    filepath = Path(filepath)
    raw = json.loads(filepath.read_text(encoding="utf-8"))
    table = find_ohlcv_table(raw)

    if table is None:
        logger.error(f"[EXTRACT] {date_str} 找不到收盤行情 table")
        return []

    fields = table["fields"]
    data = table["data"]

    # 建立欄位名稱 → index 映射
    field_indices = {}
    for zh_name, en_name in config.FIELD_MAP.items():
        try:
            field_indices[en_name] = fields.index(zh_name)
        except ValueError:
            logger.error(f"[EXTRACT] 欄位 '{zh_name}' 不存在於 fields: {fields}")
            return []

    rows = []
    for row in data:
        code = row[field_indices["code"]].strip()

        # 過濾: 只保留一般股票 + ETF
        if not config.CODE_PATTERN.match(code):
            continue

        record = {"date": date_str}
        for en_name, idx in field_indices.items():
            value = row[idx].strip()
            if en_name in ("code", "name"):
                record[en_name] = value
            else:
                record[en_name] = clean_number(value)

        rows.append(record)

    logger.info(f"[EXTRACT] {date_str}: {len(rows)} 筆 (from {len(data)} total)")
    return rows


def save_csv(rows: list[dict], filepath: str | Path) -> Path:
    """將擷取的資料儲存為 CSV"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"[CSV] 寫入 {filepath} ({len(rows)} rows)")
    return filepath


def extract_and_save(
    json_path: str | Path,
    date_str: str,
    output_dir: str | Path = config.OUTPUT_DIR,
) -> Path | None:
    """擷取 + 儲存 CSV，一步完成"""
    rows = extract_day(json_path, date_str)
    if not rows:
        return None

    csv_path = Path(output_dir) / f"{date_str}.csv"
    return save_csv(rows, csv_path)
