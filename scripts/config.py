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

# 過濾規則: 一般股票 (4碼數字) + ETF (00開頭 4~6碼)
import re
CODE_PATTERN = re.compile(r"^\d{4}$|^00\d{2,4}$")

# 目錄
DATA_DIR = "data"
OUTPUT_DIR = "output"
