# tw-stock-data-release

台灣證券交易所 (TWSE) 每日收盤行情資料，提供可直接下載的 CSV 壓縮檔。

## 資料內容

- 資料源: TWSE MI_INDEX (每日收盤行情)
- 範圍: 依股票代號與名稱篩選出的 TWSE/TPEX 標的
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

## 股票篩選規則

TWSE 與 TPEX 使用相同篩選規則:

- `code` 符合 `^[1-9][0-9]{3}$`
- `code` 符合 `^00[0-9A-Z]{2,4}$`
- `name` 不可符合字尾 `N`, `DR`, `R1`, `R2`, `特`, `售[0-9]{2}`, `購[0-9]{2}`

### CSV 範例

```csv
date,code,name,volume,open,high,low,close
20251124,006208,富邦台50,162722018,60.10,60.30,59.65,59.70
20251124,2330,台積電,88861648,1400.00,1405.00,1375.00,1375.00
```

## 本地回填與打包

### TWSE

```bash
# 預設: 20040211 ~ 20260404
python -m scripts.backfill

# 指定日期區間
python -m scripts.backfill --start 20240101 --end 20241231

# 只將 raw data 轉成每日 CSV，不合併、不產生 zip
python -m scripts.backfill --extract-only

# 只做合併打包，不讀取 raw data (使用既有每日 CSV)
python -m scripts.backfill --merge-only

# 以週為單位打包 (weekly_YYYY_Www)
python -m scripts.backfill --merge-period week

# 以年為單位打包 (yearly_YYYY)
python -m scripts.backfill --merge-period year

# 範例
python -m scripts.backfill --source-dir "D:\Twse Data\DailyClose" --start 20040211 --end 20251231 --extract-only
```

TWSE 本地流程只讀取 `--source-dir` 內既有的 `YYYYMMDD.txt` 或 `YYYYMMDD.json` 原始檔，不會下載資料。

主要參數:

- `--start`: 起始日期，格式 `YYYYMMDD`
- `--end`: 結束日期，格式 `YYYYMMDD`
- `--source-dir`: 原始檔目錄，預設 `.`
- `--output-dir`: 每日 CSV 輸出目錄，預設 `output`
- `--zip-dir`: zip 輸出目錄，預設 `releases`
- `--merge-period`: 合併週期，可用 `week` 或 `year`
- `--extract-only`: 只將 raw data 轉成每日 CSV，不做合併打包
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

# 只將 raw data 轉成每日 CSV，不合併、不產生 zip
python -m scripts.tpex_backfill --extract-only

# 只做合併打包，不讀取 raw data (使用既有每日 CSV)
python -m scripts.tpex_backfill --merge-only --output-dir output_tpex --zip-dir releases_tpex

# 以週為單位打包 (weekly_YYYY_Www)
python -m scripts.tpex_backfill --merge-period week

# 以年為單位打包 (yearly_YYYY)
python -m scripts.tpex_backfill --merge-period year

# 範例
python -m scripts.tpex_backfill --source-dir "D:\Tpex Data\DailyClose" --start 20070102 --end 20251231 --extract-only
python -m scripts.tpex_backfill --source-dir "D:\Tpex Data\DailyClose" --start 20260102 --end 20260621

```

主要參數:

- `--start`: 起始日期，格式 `YYYYMMDD`，預設 `20070102`
- `--end`: 結束日期，格式 `YYYYMMDD`，預設 `20260404`
- `--source-dir`: 原始檔目錄，預設 `.`
- `--output-dir`: 每日 CSV 輸出目錄，預設 `output_tpex`
- `--zip-dir`: zip 輸出目錄，預設 `releases_tpex`
- `--merge-period`: 合併週期，可用 `week` 或 `year`
- `--extract-only`: 只將 raw data 轉成每日 CSV，不做合併打包
- `--validation-log`: 驗證失敗紀錄，預設 `logs/tpex_validation_failures.log`
- `--merge-only`: 只合併既有每日 CSV

產生檔案:

- 每日 CSV: `{output-dir}/YYYYMMDD.csv`
- 週包: `{zip-dir}/weekly_YYYY_Www.zip`
- 年包: `{zip-dir}/yearly_YYYY.zip`
- 驗證失敗紀錄: `{validation-log}`

### TWSE + TPEX 合併打包

`scripts.merge_markets` 只讀取每日 CSV，不讀 raw data。它會讀取 TWSE/TPEX 的 `{output-dir}/YYYYMMDD.csv`，依 `--merge-period` 合併成單一 zip。

建議流程:

```bash
# 先分別產出 TWSE/TPEX 每日 CSV，不產生市場個別 zip
python -m scripts.backfill --extract-only --source-dir twse_raw --output-dir output --start 20070101 --end 20071231
python -m scripts.tpex_backfill --extract-only --source-dir tpex_raw --output-dir output_tpex --start 20070101 --end 20071231

# 再合併兩個市場的每日 CSV，產生 zip
python -m scripts.merge_markets --twse-dir output --tpex-dir output_tpex --output-dir releases_all --merge-period year --start 20040211 --end 20171231
```

主要參數:

- `--twse-dir`: TWSE 每日 CSV 目錄，預設 `output`
- `--tpex-dir`: TPEX 每日 CSV 目錄，預設 `output_tpex`
- `--output-dir`: 合併後 zip 輸出目錄，預設 `releases_all`
- `--merge-period`: 輸出合併週期，可用 `week` 或 `year`
- `--start`: 合併資料起始日期，格式 `YYYYMMDD`
- `--end`: 合併資料結束日期，格式 `YYYYMMDD`

產生檔案:

- 週包: `{output-dir}/weekly_YYYY_Www.zip`
- 年包: `{output-dir}/yearly_YYYY.zip`

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
  merge_markets.py       # 合併 TWSE/TPEX 每日 CSV 並打包
README.md
```
