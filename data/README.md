# Data contract

## Public baseline

- A-share and index prices: downloaded through AkShare's Eastmoney adapters.
- Lithium carbonate futures: Sina's GFEX LC0 main-continuous series downloaded through AkShare. It is a vendor-constructed continuous series; the official GFEX historical-data page is retained as the exchange reference.
- CATL filings: official CATL investor-relations PDFs; the repository stores URLs, hashes, release dates, and extracted facts rather than committing large PDFs.

Run `make filings` to download the official PDFs to the ignored `data/external/filings/` directory and verify every file against `data/manual/filing_sources.csv`.

## Optional paid-source imports

Place exports in `data/external/`. These files are ignored by Git.

### `wind_market_daily.csv`

Required columns: `date, symbol, close, volume`. Optional: `open, high, low, amount, market_cap, pe_ttm, pb, ev_ebitda`.

### `smm_lithium_daily.csv`

Required columns: `date, series, price, unit`. Use a stable battery-grade lithium-carbonate series and do not splice methodologies without a documented break.

### `industry_monthly.csv`

Required columns: `month, metric, value, unit, source, release_date`. Candidate metrics include China NEV sales, global battery installations, CATL installation share, and ESS shipments.

Every external row must have a source and a release date. The build step will reject data released after the research cutoff.

## Systematic-equity extension

Run `make systematic-download` to construct the ignored raw assets below.

### `systematic_membership.parquet`

Required columns: `fund_symbol,snapshot_date,available_date,year,quarter,symbol,name,weight_pct,rank`.

The public baseline uses the top 50 disclosed Q2 and Q4 holdings of ETF 561910. Q2 snapshots receive a 60-calendar-day publication delay and Q4 snapshots a 90-day delay. These holdings are a conservative public proxy for the tracked index's historical membership, not an official immutable constituent history.

### `systematic_market_daily.parquet`

Required columns: `date,symbol,open_raw,high_raw,low_raw,close_raw,volume_raw,open_adjusted,high_adjusted,low_adjusted,close_adjusted,adjustment_factor`.

Yahoo Finance is the primary source. Tencent history via AkShare is the fallback for Shanghai/Shenzhen securities absent from Yahoo, including historical delistings. Raw prices and volume support liquidity/cost calculations; adjusted prices support returns. Benchmark symbol 510300 is a liquid CSI 300 ETF proxy rather than the total-return index.

### `systematic_fundamentals_pit.parquet`

Required keys: `symbol,report_date,notice_date,available_date`. The current public adapter also stores revenue, profit, ROE, gross margin, net margin and debt ratio.

A record may enter a monthly cross-section only when both its notice and availability dates are no later than the signal date. This blocks simple announcement-date leakage, but it cannot undo later vendor restatements or backfills.

### Manual comparability map

`manual/systematic_industry_groups.csv` records every symbol in the membership union, the analyst-assigned broad value-chain group, the include/exclude flag and the reason. It is not an official industry taxonomy. Excluded names remain visible in the mapping and raw membership history for audit.

### Generated assets

- `processed/systematic_monthly_panel.parquet`: baseline one-trading-day-lag features and labels;
- `processed/systematic_monthly_panel_lag2.parquet`: additional timing-lag robustness panel;
- `../reports/tables/systematic_*.csv`: small, committed IC, quantile, portfolio, trade and contribution ledgers;
- `../reports/systematic_summary.json`: canonical hashes, results and failure checks.

Raw and processed Parquet files are ignored because of size. Their content hashes, provider metadata and parameters are recorded in `source_manifest.json`.
