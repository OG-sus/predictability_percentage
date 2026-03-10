"""
finance_stream_sync.py — Live Finance Ticker Sync
===================================================
Keeps your Finance Google Sheet tab updated automatically with live
(15-min delayed) market prices and FSR scores via yfinance.

Unlike NBA/CBB/MLB sync scripts that replay historical data game-by-game,
this script:
  • Updates ALL rows marked Is_Live=TRUE at once
  • Loops forever on a configurable interval (default: every 5 minutes)
  • No manual intervention required — just leave it running

Setup:
  1. In your Google Sheet, add a tab named "Finance"
  2. Add rows with this format (same A-L column structure as NBA):
       A (Name): BTC-USD
       B (Score): [auto-filled]
       C (Avg):   [auto-filled]
       D (Type):  1d   ← yfinance interval: 1h, 1d, 1wk
       E (Is_Live): TRUE
       F (Featured): TRUE  ← only one should be TRUE for the main chart
       K (Real_Data): [auto-filled]
       L (Target): [auto-filled]
  3. Run: python finance_stream_sync.py

Suggested tickers: BTC-USD, ETH-USD, SPY, QQQ, NVDA, TSLA, AAPL, GLD

Intervals (column D):
  1h  → last 7 days of hourly data   (intraday feel)
  1d  → last 90 days of daily closes (trend view)
  1wk → last 2 years of weekly data  (macro view)
"""

import time
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fsr import calculate_predictability

# --- CONFIGURATION ---
SHEET_ID         = "1F3V-nmqchQE2-pauoRCVWDdZKLUIOLbSt1qeXvcUz6o"  # Same sheet as NBA
SHEET_TAB_NAME   = "Finance"
CREDENTIALS_FILE = "service_account.json"
K_FACTOR         = 2.0      # Finance — strict scoring
REFRESH_MINUTES  = 5        # How often to refresh all live tickers
DATA_POINTS      = 30       # Number of price points to use for scoring & chart

# Interval → (yfinance period, yfinance interval) mapping
INTERVAL_MAP = {
    '1h':  ('7d',  '1h'),
    '1d':  ('3mo', '1d'),
    '1wk': ('2y',  '1wk'),
}
DEFAULT_INTERVAL = '1d'

# Column indices (match NBA/CBB/MLB sheet layout)
COL_NAME      = 1
COL_SCORE     = 2
COL_AVG       = 3
COL_TYPE      = 4   # stores the yfinance interval e.g. "1d"
COL_IS_LIVE   = 5
COL_FEATURED  = 6
COL_TITLE     = 9
COL_SUBTITLE  = 10
COL_REAL_DATA = 11
COL_TARGET    = 12


def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        raise RuntimeError(f"Tab '{SHEET_TAB_NAME}' not found. Add it to your Google Sheet first.")


def fetch_prices(ticker_symbol, interval='1d'):
    """Fetch the last DATA_POINTS close prices for a ticker. Returns [] on failure."""
    period, yf_interval = INTERVAL_MAP.get(interval, INTERVAL_MAP[DEFAULT_INTERVAL])
    try:
        data = yf.download(ticker_symbol, period=period, interval=yf_interval, progress=False)
        if data.empty:
            print(f"  [{ticker_symbol}] No data returned from yfinance.")
            return []

        if hasattr(data.columns, 'levels'):
            closes = data['Close'][ticker_symbol]
        else:
            closes = data['Close']

        closes = closes.dropna().tail(DATA_POINTS)
        return [round(float(p), 4) for p in closes.tolist()]
    except Exception as e:
        print(f"  [{ticker_symbol}] yfinance error: {e}")
        return []


def update_all_live_rows(worksheet):
    """Fetch fresh prices and FSR scores for every Is_Live=TRUE row."""
    all_rows = worksheet.get_all_values()
    updated  = 0

    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) < COL_IS_LIVE or row[COL_IS_LIVE - 1].upper() != 'TRUE':
            continue

        ticker   = row[COL_NAME - 1].strip().upper()
        interval = row[COL_TYPE - 1].strip() or DEFAULT_INTERVAL
        featured = row[COL_FEATURED - 1].upper() == 'TRUE' if len(row) >= COL_FEATURED else False

        if not ticker:
            continue

        print(f"  Updating {ticker} (interval={interval}, featured={featured})...")
        prices = fetch_prices(ticker, interval)

        if not prices:
            print(f"  [{ticker}] Skipped — no data.")
            continue

        score   = calculate_predictability(prices, k=K_FACTOR)
        avg     = round(sum(prices) / len(prices), 4)
        current = prices[-1]
        change  = round(current - avg, 4)
        change_pct = round((change / avg) * 100, 2) if avg else 0.0

        real_data_str = ",".join(map(str, prices))
        trend = "⬆" if change >= 0 else "⬇"

        batch = {
            f'B{i}': f"{score:.2f}",
            f'C{i}': f"{current:.4f}",
            f'K{i}': real_data_str,
            f'L{i}': f"{avg:.4f}",
        }

        if featured:
            batch[f'G{i}'] = f"{ticker}  {trend}  ${current:,.2f}"
            batch[f'H{i}'] = f"Score: {score:.1f}/100  |  Avg: ${avg:,.2f}  |  {change_pct:+.2f}%"
            batch[f'I{i}'] = ticker
            batch[f'J{i}'] = f"Predictability Score™: {score:.1f}/100"

        for cell, value in batch.items():
            worksheet.update_acell(cell, value)

        print(f"  [{ticker}] Price=${current:.4f} | Avg=${avg:.4f} | Score={score:.2f}/100")
        updated += 1
        time.sleep(1)  # Avoid Google Sheets API rate limits

    return updated


def main():
    print("=" * 50)
    print(" Finance Stream Sync — Predictability Score™")
    print(f" Sheet tab : {SHEET_TAB_NAME}")
    print(f" Refresh   : every {REFRESH_MINUTES} minutes")
    print(f" K-Factor  : {K_FACTOR} (Finance/strict)")
    print(f" Data pts  : {DATA_POINTS} price points per ticker")
    print("=" * 50)

    worksheet = connect_to_sheet()
    print(f"Connected to Google Sheet tab '{SHEET_TAB_NAME}'\n")

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n[Cycle {cycle}] Refreshing all live tickers...")
            count = update_all_live_rows(worksheet)
            print(f"[Cycle {cycle}] Done — {count} ticker(s) updated. Next refresh in {REFRESH_MINUTES} min.")
            time.sleep(REFRESH_MINUTES * 60)

    except KeyboardInterrupt:
        print("\nFinance sync stopped.")


if __name__ == "__main__":
    main()
