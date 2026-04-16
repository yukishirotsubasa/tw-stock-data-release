"""
TWSE JSON 資料驗證器
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """驗證失敗"""
    pass


def validate(filepath: str | Path, expected_date: str) -> dict:
    """
    驗證 TWSE MI_INDEX JSON 檔案。

    檢查項目:
      1. JSON 格式正確
      2. stat == "OK"
      3. date == expected_date
      4. 存在含「收盤行情」的 table
      5. fields 包含所有需要的欄位

    Args:
        filepath: JSON 檔案路徑
        expected_date: 預期日期 YYYYMMDD

    Returns:
        解析後的 JSON dict

    Raises:
        ValidationError: 驗證失敗
    """
    filepath = Path(filepath)

    # 1. JSON parse
    try:
        raw = json.loads(filepath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValidationError(f"JSON 解析失敗: {e}")

    # 2. stat check
    stat = raw.get("stat", "")
    if stat != "OK":
        raise ValidationError(
            f"stat='{stat}' (非交易日或資料不存在)"
        )

    # 3. date check
    date = raw.get("date", "")
    if date != expected_date:
        raise ValidationError(
            f"date mismatch: 預期 {expected_date}, 實際 {date}"
        )

    # 4. 找收盤行情 table
    target_table = find_ohlcv_table(raw)
    if target_table is None:
        raise ValidationError(
            f"找不到含 '{config.TARGET_TABLE_KEYWORD}' 的 table"
        )

    # 5. 檢查必要欄位
    fields = target_table.get("fields", [])
    missing = [f for f in config.FIELD_MAP if f not in fields]
    if missing:
        raise ValidationError(f"缺少欄位: {missing}")

    logger.info(f"[VALID] {expected_date} 驗證通過 ({len(target_table['data'])} rows)")
    return raw


def find_ohlcv_table(data: dict) -> dict | None:
    """從 MI_INDEX JSON 中找到含「收盤行情」的 table"""
    for table in data.get("tables", []):
        title = table.get("title", "")
        if config.TARGET_TABLE_KEYWORD in title:
            return table
    return None
