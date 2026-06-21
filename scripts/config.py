"""
tw-stock-data-release 常數定義
"""

# TWSE API
TWSE_MI_INDEX_URL = (
    "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    "?type=ALL&response=json&date={date}"
)

# Request throttling
REQUEST_DELAY_SEC = 5       # 每次請求間隔
MAX_RETRIES = 3             # 最大重試次數
BACKOFF_BASE_SEC = 10       # Exponential backoff 基數

# 資料擷取
TARGET_TABLE_KEYWORD = "收盤行情"

# OHLCV 欄位映射 (field name → output column name)
FIELD_MAP = {
    "證券代號": "code",
    "證券名稱": "name",
    "成交股數": "volume",
    "開盤價":   "open",
    "最高價":   "high",
    "最低價":   "low",
    "收盤價":   "close",
}

# CSV 輸出欄位順序
CSV_COLUMNS = ["date", "code", "name", "volume", "open", "high", "low", "close"]

import re

# 過濾規則: 一般股票 (1~9 開頭 4 碼) + 00 開頭商品 (總長度 4~6 碼)
COMMON_STOCK_CODE_PATTERN = re.compile(r"^[1-9][0-9]{3}$")
ETF_CODE_PATTERN = re.compile(r"^00[0-9A-Z]{2,4}$")
CODE_PATTERN = re.compile(r"^(?:[1-9][0-9]{3}|00[0-9A-Z]{2,4})$")
EXCLUDED_NAME_SUFFIX_PATTERN = re.compile(r"(?:N|DR|R1|R2|特|售[0-9]{2}|購[0-9]{2})$")


def is_included_security(code: str, name: str) -> bool:
    code_value = code.strip().upper()
    name_value = name.strip()

    if not CODE_PATTERN.fullmatch(code_value):
        return False

    return EXCLUDED_NAME_SUFFIX_PATTERN.search(name_value) is None

# 目錄
DATA_DIR = "data"
OUTPUT_DIR = "output"
