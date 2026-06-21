# tw-stock-data-release

台灣證券交易所 (TWSE) 每日收盤行情資料，提供可直接下載的 CSV 壓縮檔。

## 資料內容

- 資料源: TWSE MI_INDEX (每日收盤行情)
- 範圍: 上市股票 + ETF
- 欄位: `date`, `code`, `name`, `volume`, `open`, `high`, `low`, `close`
- 格式: CSV (UTF-8, 含 header)，壓縮為 zip
- 更新: 每週六自動發布至 [Releases](../../releases)

## 命名規則

- Dataset Tag (GitHub Release tag): `daily-close-csv`
- Weekly 打包檔名: `weekly_YYYY_Www.zip`
  - 例: `weekly_2026_W15.zip`
- Yearly 打包檔名: `yearly_YYYY.zip`
  - 例: `yearly_2025.zip`

## 使用方式

從 [Releases](../../releases) 頁面下載最新 zip，解壓後即為 CSV。

### CSV 範例

```csv
date,code,name,volume,open,high,low,close
20251124,0050,元大台灣50,162722018,60.10,60.30,59.65,59.70
20251124,2330,台積電,88861648,1400.00,1405.00,1375.00,1375.00
```

## 本地回填與打包

### TWSE

```bash
# 預設: 20040211 ~ 20260404
python -m scripts.backfill

# 指定日期區間
python -m scripts.backfill --start 20240101 --end 20241231

# 只做合併打包 (使用既有 CSV)
python -m scripts.backfill --merge-only

# 以週為單位打包 (weekly_YYYY_Www)
python -m scripts.backfill --merge-period week

# 以年為單位打包 (yearly_YYYY)
python -m scripts.backfill --merge-period year
```

TWSE 本地流程只讀取 `--source-dir` 內既有的 `YYYYMMDD.txt` 或 `YYYYMMDD.json` 原始檔，不會下載資料。

主要參數:

- `--start`: 起始日期，格式 `YYYYMMDD`
- `--end`: 結束日期，格式 `YYYYMMDD`
- `--source-dir`: 原始檔目錄，預設 `.`
- `--output-dir`: 每日 CSV 輸出目錄，預設 `output`
- `--zip-dir`: zip 輸出目錄，預設 `releases`
- `--merge-period`: 合併週期，可用 `week` 或 `year`
- `--validation-log`: 驗證失敗紀錄，預設 `logs/validation_failures.log`
- `--merge-only`: 只合併既有每日 CSV

產生檔案:

- 每日 CSV: `{output-dir}/YYYYMMDD.csv`
- 週包: `{zip-dir}/weekly_YYYY_Www.zip`
- 年包: `{zip-dir}/yearly_YYYY.zip`
- 驗證失敗紀錄: `{validation-log}`

### TPEX

TPEX 本地流程只讀取 `--source-dir` 內既有的 `YYYYMMDD.txt` / `YYYYMMDD.csv` / `YYYYMMDD.html` / `YYYYMMDD.htm` 原始檔，不會下載資料。

支援格式:

- 2007 年 7 月前的 HTML table
- 2007 年 7 月起的 CSV 文字內容
- CSV 無資料日 (`共0筆`) 會略過，不視為驗證失敗

```bash
# 使用預設輸出路徑 output_tpex / releases_tpex
python -m scripts.tpex_backfill --source-dir "D:\Tpex Data\DailyClose" --start 20070102 --end 20111231

# 指定正式輸出路徑
python -m scripts.tpex_backfill --source-dir tpex_raw --output-dir output_tpex --zip-dir releases_tpex

# 只做合併打包 (使用既有 TPEX 每日 CSV)
python -m scripts.tpex_backfill --merge-only --output-dir output_tpex --zip-dir releases_tpex

# 以週為單位打包 (weekly_YYYY_Www)
python -m scripts.tpex_backfill --merge-period week

# 以年為單位打包 (yearly_YYYY)
python -m scripts.tpex_backfill --merge-period year

# 範例
python -m scripts.tpex_backfill --source-dir "D:\Tpex Data\DailyClose" --start 20070102 --end 20251231 --merge-period year
python -m scripts.tpex_backfill --source-dir "D:\Tpex Data\DailyClose" --start 20260102 --end 20260621 --merge-period week

```

主要參數:

- `--start`: 起始日期，格式 `YYYYMMDD`，預設 `20070102`
- `--end`: 結束日期，格式 `YYYYMMDD`，預設 `20260404`
- `--source-dir`: 原始檔目錄，預設 `.`
- `--output-dir`: 每日 CSV 輸出目錄，預設 `output_tpex`
- `--zip-dir`: zip 輸出目錄，預設 `releases_tpex`
- `--merge-period`: 合併週期，可用 `week` 或 `year`
- `--validation-log`: 驗證失敗紀錄，預設 `logs/tpex_validation_failures.log`
- `--merge-only`: 只合併既有每日 CSV

產生檔案:

- 每日 CSV: `{output-dir}/YYYYMMDD.csv`
- 週包: `{zip-dir}/weekly_YYYY_Www.zip`
- 年包: `{zip-dir}/yearly_YYYY.zip`
- 驗證失敗紀錄: `{validation-log}`

## 專案結構

```text
.github/workflows/
  weekly-update.yml      # 每週自動更新與發版
scripts/
  config.py              # 常數設定
  downloader.py          # 下載 TWSE 原始資料
  validator.py           # 資料驗證
  extractor.py           # 萃取 OHLCV
  merger.py              # 合併與壓縮
  weekly.py              # 每週流程 (GitHub Actions)
  backfill.py            # 歷史回填與批次打包
  tpex_backfill.py       # TPEX 本地回填與批次打包
README.md
```
