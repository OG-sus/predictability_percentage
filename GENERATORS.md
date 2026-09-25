# Generator Command Reference

Every generator in this folder, what it pulls, and how to run it.
Run everything from the project folder:

```powershell
cd "C:\Users\RMDon\PycharmProjects\FSR_c_%"
```

Legend: **REAL** = live data from a real source · **HARDCODED** = real, sourced numbers typed into the script · **SYNTHETIC** = made-up/simulated data (not for Shorts)

k-factor standards: **2.0** finance · **1.0** general · **0.5** sports

---

## 0. scanner_gen.py — let the engine pick the topic · REAL

Runs a sliding window over ~55 real series (Wikipedia attention, FRED, stocks/crypto, top airing anime)
and ranks them by how far their stability dropped recently vs. their own normal.
```
python scanner_gen.py                          # scan everything, top 10
python scanner_gen.py --top 20 --csv           # save all results to scan_results.csv
python scanner_gen.py --only wiki fred         # sources: wiki, fred, market, anime
python scanner_gen.py --add-wiki "Hollow Knight: Silksong"   # extra articles this run
```
Edit the `WIKI_ARTICLES` / `FRED_SERIES` / `MARKET_TICKERS` lists at the top of the file to change the basket.
Each result prints the exact generator command to dig into it.

---

## 1. Pick-any-topic generators (real data, you choose what to run)

These print the score plus a `--- Series ---` line to paste into the website calculator.

### FRED_gen.py — any Federal Reserve economic series · REAL · k=2.0
```
python FRED_gen.py REVOLSL --since 2006                 # credit card debt, 20 years
python FRED_gen.py DGS10 --since 2006 --window 100      # 10-yr Treasury + sliding-window lows
python FRED_gen.py GASDESW --last 500 --csv             # diesel, last 500 points, save CSV
python FRED_gen.py UNRATE --last 24                     # last 24 points only
python FRED_gen.py --search "credit card"               # find series IDs by keyword
```
Options: `--since 2006 | 2006-08 | 2006-08-15` · `--last N` · `--window N` · `--k` · `--csv`
Handy IDs: REVOLSL (card debt) · TERMCBCCALLNS (card interest) · DRCCLACBS (card delinquency) · DGS10 · MORTGAGE30US · CPIAUCSL · UNRATE · GASDESW

### pageviews_gen.py — Wikipedia pageviews for any article · REAL · k=1.0
```
python pageviews_gen.py "Stranger Things"                    # last 90 days, daily
python pageviews_gen.py "Lipstick effect" --days 1095 --weekly   # 3 years, weekly totals
python pageviews_gen.py "One Piece" --compare "Naruto"       # two articles side by side
python pageviews_gen.py "Stranger Things" --csv
```
Options: `--days N` (back to 2015) · `--weekly` · `--compare ARTICLE2` · `--k` · `--csv`
Watch for: article renames/moves (history stays on the old title — e.g. "Pumpkin spice latte" looks like a fake explosion).

### anilist_gen.py — anime audiences from AniList · REAL · k=1.0
```
python anilist_gen.py --top                                  # 10 most-trending anime right now
python anilist_gen.py "Re:ZERO Season 4"                     # people currently watching (default)
python anilist_gen.py "Re:ZERO Season 4" --metric trending   # hype spikes on episode days
python anilist_gen.py "Re:ZERO Season 4" --days 60 --csv
```
Options: `--metric watching | trending | popularity | score` · `--days N` · `--k` · `--csv` (saves `<show>_anilist_<metric>.csv`)
Prints episode-drop dates and **warns about missing days**.

### search_hype_gen.py — Google Trends search interest · REAL · k=1.0
```
python search_hype_gen.py "Taylor Swift"                     # ~90 days, daily
python search_hype_gen.py "Taylor Swift" --window recent     # last 7 days, hourly
python search_hype_gen.py "Grand Theft Auto VI" --compare "GTA 6"
```
Options: `--window broad | recent` · `--compare TERM2` · `--k`
Note: Google scales every solo query to its own 0–100 — use `--compare` to compare two terms fairly.
Needs `pip install pytrends` — it's not installed in `.venv` right now.

### stock_fsr_chart.py — single stock chart (YouTube edition) · REAL (yfinance)
```
python stock_fsr_chart.py NVDA
python stock_fsr_chart.py TSLA
```

### weather_compare.py — year-over-year weather stability · REAL (Open-Meteo)
```
python weather_compare.py --cities Denver "Los Angeles"
python weather_compare.py --cities Denver --days 75 --end-date 2026-03-21
python weather_compare.py --cities Denver --metric vpd --days 30
python weather_compare.py --cities Denver --export-series          # CSV for the calculator
```
More options: `--unit celsius` · `--k` · `--window-size N` · `--no-chart` · `--csv FILE`

### texas_av_gen.py — Texas robotaxi fleet sizes (Tesla, Waymo, Zoox, Avride) · REAL · k=2.0
```
python texas_av_gen.py                    # all operators, daily series since 2026-05-28
python texas_av_gen.py tesla --models     # Model Y vs Cybercab, first-registered dates
python texas_av_gen.py --csv              # texas_av_fleet.csv, one column per operator
```
Source: texasavtracker.com feed of the TxDMV AV registry (statewide only — no per-city counts). Credit them in descriptions.
Watch for: same-day jumps across companies (e.g. 2026-09-02) are likely DMV batch processing — say "registered", not "deployed".

### eth_yt_chart.py — Ethereum gas fees per block · REAL
```
python eth_yt_chart.py            # last 100 blocks
python eth_yt_chart.py 150        # custom block count
```

---

## 2. Real data, fixed topic (just run it)

| Command | What it charts | Source | Saves |
|---|---|---|---|
| `python bitcoin_gen.py` | Bitcoin on-chain transaction volume, 30-day window | blockchain.info | bitcoin_gen.png |
| `python oil_yt_chart.py` | Oil market comparison, 1 year, k=2.0 | yfinance | oil_yt_chart.png |
| `python ai_prediction_audit.py` | Wall Street AI consensus audit, k=2.0 | yfinance | ai_prediction_audit.png |
| `python inflation_gen.py` | US CPI inflation, 6-month window | BLS | inflation_gen.png |
| `python jobs_gen.py` | Unemployment + payrolls, 6-month window | BLS | jobs_gen.png |
| `python demographics_gen.py` | US birth rate + divorce rate | World Bank | 3 PNGs |
| `python census_gen.py` | Monthly retail trade, 2000–now (needs CENSUS_API_KEY) | Census Bureau | prints table |
| `python nasadonki_gen.py` | Geomagnetic storm Kp index, 10 years (needs NASA_API_KEY) | NASA DONKI | prints score |
| `python hurricane_gen.py` | Atlantic hurricane seasons, 10-yr window | NOAA (embedded) | hurricane_gen.png |
| `python analyze_mortgage_data.py` | 30-yr mortgage rate | MORTGAGE30US.csv | mortgage_stability_analysis.png |
| `python lol_msi_gen.py` | League of Legends MSI 2025 series/games | lol.fandom.com | lol_msi_fsr_results.csv |

---

## 3. Price-shock Shorts charts (HARDCODED real dated prices, Shorts-sized 1080x1920)

Edit the price list inside the file to update, then run.

| Command | Saves |
|---|---|
| `python ps5_price_shock.py` | ps5_price_shock.png |
| `python rtx5090_price_shock.py` | rtx5090_price_shock.png |
| `python ddr5_price_shock.py` | ddr5_price_shock.png |
| `python dgs10_yield_shock.py` | dgs10_yield_shock.png |
| `python gpu_price_trends.py` | gpu_price_trends.png (2022–2025, NVIDIA/AMD/Intel) |

---

## 4. Interactive (asks you questions when it runs)

| Command | It asks for | Source |
|---|---|---|
| `python nba_data_gen.py` | player name, stat (PTS/REB/AST), # games | nba_api |
| `python nfl_data_gen.py` | player name, stat (Pass_Yds/Rush_Yds), season | pro-football-reference |
| `python nhl_data_gen.py` | player name, stat (goals/shots), season end year | hockey-reference |
| `python mlb_data_gen.py` | player name, stat (H/HR/SO), season, # games | pybaseball |
| `python cbb_data_gen.py` | college player, stat, season, # games | ESPN / sports-reference |
| `python golf_gen.py` | mode 1–3, player or manual round scores | ESPN |
| `python esports_gen.py` | mode 1–4, search term, player, # matches | Twitch |
| `python social_gen.py` | mode 1–4, subreddit, days, comments/posts | Reddit / YouTube |
| `python marketing_gen.py` | mode 1–2, CSV path, metric + date columns | your CSV / yfinance |
| `python base_data_gen.py` | stat (TX_COUNT/GAS/BLOCK_TIME), # blocks, live mode | Base + Ethereum RPC |

---

## 5. Sports charts (real data, options)

```
python daily_slate.py                         # today's MLB slate
python daily_slate.py 2026-05-10              # specific date
python batter_fsr_charts.py --date 2026-03-26
python umpire_fsr_charts.py --leaderboard
python umpire_fsr_charts.py --leaderboard --days 30
python umpire_fsr_charts.py --umpire "Angel Hernandez"
python mlb_326_2026_graphs.py --game-date 2026-03-26
python opening_day_mlb_graphs.py --game-date 2026-03-26
python soccer_fsr_chart.py "USA" "Paraguay"
python nba_mvp_gen.py                         # SGA vs Jokic, Wemby vs Luka (2025-26)
python nba_mvp_radar.py                       # MVP radar chart
python kaggle_nba_gen.py                      # league-wide player stability CSV
python nhl_playoff_compare.py                 # 2026 NHL playoff comparison
python parlay_fsr_chart.py                    # same-game parlay chart
```

---

## 6. Stream + agents

```
powershell -File stream_infra\run_stream.ps1                    # 24/7 ticker stream (Quick Sync, 20fps)
python ticker_feed_writer.py --rotate-seconds 8 --columns 3 --rows-per-col 4
python fsr_data_agent.py --interval 3600 --threshold 70         # periodic FSR checker (Bitcoin only so far)
```

---

## 7. SYNTHETIC — simulated data, don't use for Shorts

`synthetic_gen.py` · `soccer_gen.py` · `tennis_gen.py` · `engineering_data_gen.py` (bridge sensor sim) · `analyze_tennis_match.py` · `analyze_ai_underwriting.py`

These are demos/tests. They ask for a mode and parameters, then generate random series.
