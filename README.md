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
README.md
```
